<template>
  <div>
    <p class="map-hint">{{ t('page.settings.mapHint') }}</p>

    <div
      ref="mapElement"
      class="map"
      :class="{ 'is-expanded': expanded }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerRelease"
      @pointercancel="onPointerRelease"
      @dblclick="onDoubleClick"
      @wheel="onWheel"
    >
      <div class="map-tiles" :style="tileLayerStyle">
        <img
          v-for="tile in tiles"
          :key="tile.key"
          class="map-tile"
          :src="tile.src"
          :style="{ left: tile.left, top: tile.top }"
          alt=""
          draggable="false"
          @error="offline = true"
        />
      </div>

      <div v-if="pinStyle" class="map-pin" :style="pinStyle"></div>

      <!-- Two buttons rather than one that changes label, so each state keeps its own
           translated tooltip and CSS decides which one is showing. -->
      <div class="map-zoom">
        <button
          v-if="!expanded"
          v-bs-tooltip="t('page.settings.mapExpand')"
          type="button"
          class="map-button"
          :aria-label="t('page.settings.mapExpand')"
          @click="toggleExpanded"
        >
          <i class="bi bi-arrows-fullscreen"></i>
        </button>
        <button
          v-else
          v-bs-tooltip="t('page.settings.mapCollapse')"
          type="button"
          class="map-button"
          :aria-label="t('page.settings.mapCollapse')"
          @click="toggleExpanded"
        >
          <i class="bi bi-fullscreen-exit"></i>
        </button>
        <button
          v-bs-tooltip="t('page.settings.mapZoomIn')"
          type="button"
          class="map-button"
          :aria-label="t('page.settings.mapZoomIn')"
          @click="zoomBy(1)"
        >
          <i class="bi bi-plus-lg"></i>
        </button>
        <button
          v-bs-tooltip="t('page.settings.mapZoomOut')"
          type="button"
          class="map-button"
          :aria-label="t('page.settings.mapZoomOut')"
          @click="zoomBy(-1)"
        >
          <i class="bi bi-dash-lg"></i>
        </button>
      </div>

      <p class="map-credit">
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          &copy; OpenStreetMap
        </a>
      </p>
    </div>

    <p v-if="offline" class="map-offline">{{ t('page.settings.mapOffline') }}</p>

    <button type="button" class="btn btn-outline-light btn-sm map-locate" @click="useMyLocation">
      <i class="bi bi-crosshair me-1"></i>{{ t('page.settings.useMyLocation') }}
    </button>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

// The coordinate picker. Click it to set the coordinates, and typing coordinates moves
// the pin, so the fields and the map always show the same point.
//
// The same picker the setup wizard shows, which is server-rendered Django and cannot
// share code with this app. Both are written out rather than pulled from a tile library,
// because a picker needs only the Web Mercator projection, a grid of images and a drag
// handler. The tiles come from OpenStreetMap, so a station with no internet shows an
// empty frame and a note, and the two fields still work on their own.

const TILE_SIZE = 256
const MIN_ZOOM = 2
const MAX_ZOOM = 16
// Close enough to tell one garden from the next, which is the scale this question is
// asked at.
const PLACE_ZOOM = 13
// Where a station with no coordinates starts: the whole world, so the first click can
// land anywhere.
const START_LATITUDE = 25
const START_LONGITUDE = 0
// Web Mercator cannot draw the poles, so latitude stops where the square world does.
const MAX_LATITUDE = 85.05112878
// A press that moves less than this is somebody pointing at a place, not dragging.
const DRAG_SLOP_PX = 4
// How much wheel a zoom level costs. A mouse notch is around 100 and a trackpad sends a
// stream of small ones, so this collects them rather than jumping a level each time.
const WHEEL_PER_ZOOM = 50
// Five decimals is about a metre, which is as much as anyone can point at on a map and
// more than the species list needs.
const DECIMALS = 5

function scaleAt(zoom) {
  return TILE_SIZE * 2 ** zoom
}

function worldXFromLongitude(longitude, zoom) {
  return ((longitude + 180) / 360) * scaleAt(zoom)
}

function worldYFromLatitude(latitude, zoom) {
  const bounded = Math.max(-MAX_LATITUDE, Math.min(MAX_LATITUDE, latitude))
  const sine = Math.sin((bounded * Math.PI) / 180)
  return (0.5 - Math.log((1 + sine) / (1 - sine)) / (4 * Math.PI)) * scaleAt(zoom)
}

function longitudeFromWorldX(x, zoom) {
  return (x / scaleAt(zoom)) * 360 - 180
}

function latitudeFromWorldY(y, zoom) {
  const projected = Math.PI - (2 * Math.PI * y) / scaleAt(zoom)
  return (180 / Math.PI) * Math.atan(Math.sinh(projected))
}

function rounded(value) {
  return Number(value.toFixed(DECIMALS))
}

const props = defineProps({
  latitude: { type: [Number, String], default: null },
  longitude: { type: [Number, String], default: null },
})

// One event for both, because a click on the map always sets the pair.
const emit = defineEmits(['place'])

const { t } = useI18n()

const mapElement = ref(null)
// The centre, held as world pixels at the current zoom rather than as coordinates:
// panning is then a subtraction and zooming a multiplication.
const view = ref({
  x: worldXFromLongitude(START_LONGITUDE, MIN_ZOOM),
  y: worldYFromLatitude(START_LATITUDE, MIN_ZOOM),
  zoom: MIN_ZOOM,
})
const frame = ref({ width: 0, height: 0 })
const expanded = ref(false)
const offline = ref(false)
const pinch = ref(null)

// Every finger or pen currently down, by pointer id. One is a drag, two are a pinch.
let pointers = {}
let drag = null
// A pinch ends with fingers lifting one at a time, and neither lift is somebody pointing
// at a place.
let ignoreNextPress = false
let wheelSoFar = 0
// What this map last sent out, so the watcher below can tell a click on the map from
// somebody typing in the fields.
let placed = null
let resizeObserver = null

// The pin is the value the fields hold, not a second copy of it.
const point = computed(() => {
  const latitude = Number.parseFloat(props.latitude)
  const longitude = Number.parseFloat(props.longitude)
  if (Number.isNaN(latitude) || Number.isNaN(longitude)) return null
  if (latitude < -90 || latitude > 90) return null
  if (longitude < -180 || longitude > 180) return null
  return { latitude, longitude }
})

// The world pixel drawn in the top left corner. Rounded, so a tile never lands on half a
// pixel and gets resampled for nothing.
const origin = computed(() => ({
  left: Math.round(view.value.x - frame.value.width / 2),
  top: Math.round(view.value.y - frame.value.height / 2),
}))

const tiles = computed(() => {
  const { width, height } = frame.value
  if (width === 0 || height === 0) return []
  const { left, top } = origin.value
  const zoom = view.value.zoom
  const lastIndex = 2 ** zoom - 1
  const firstX = Math.max(0, Math.floor(left / TILE_SIZE))
  const firstY = Math.max(0, Math.floor(top / TILE_SIZE))
  const lastX = Math.min(lastIndex, Math.floor((left + width) / TILE_SIZE))
  const lastY = Math.min(lastIndex, Math.floor((top + height) / TILE_SIZE))
  const wanted = []

  for (let tileY = firstY; tileY <= lastY; tileY++) {
    for (let tileX = firstX; tileX <= lastX; tileX++) {
      wanted.push({
        // Keyed by position, so panning reuses the images already loaded and only the
        // tiles that scrolled out are thrown away.
        key: `${zoom}/${tileX}/${tileY}`,
        src: `https://tile.openstreetmap.org/${zoom}/${tileX}/${tileY}.png`,
        left: `${tileX * TILE_SIZE - left}px`,
        top: `${tileY * TILE_SIZE - top}px`,
      })
    }
  }
  return wanted
})

const pinStyle = computed(() => {
  if (point.value === null || pinch.value !== null) return null
  const x = worldXFromLongitude(point.value.longitude, view.value.zoom) - origin.value.left
  const y = worldYFromLatitude(point.value.latitude, view.value.zoom) - origin.value.top
  if (x < 0 || y < 0 || x > frame.value.width || y > frame.value.height) return null
  return { left: `${x}px`, top: `${y}px` }
})

const tileLayerStyle = computed(() => {
  if (pinch.value === null) return null
  return {
    transform: `scale(${pinch.value.scale})`,
    transformOrigin: `${pinch.value.x}px ${pinch.value.y}px`,
  }
})

// The world has to be at least as big as the frame it is drawn in, or the map would sit
// in a letterbox. The small map never reaches this; the expanded one does.
function holdZoomAboveTheFrame(width, height) {
  const needed = Math.ceil(Math.log2(Math.max(width, height) / TILE_SIZE))
  const lowest = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, needed))
  if (view.value.zoom >= lowest) return
  const factor = 2 ** (lowest - view.value.zoom)
  view.value = { x: view.value.x * factor, y: view.value.y * factor, zoom: lowest }
}

// Keep the world inside the frame, so there is no way to drag off the edge into grey.
function holdInsideTheWorld(width, height) {
  const scale = scaleAt(view.value.zoom)
  view.value.x =
    scale > width ? Math.max(width / 2, Math.min(scale - width / 2, view.value.x)) : scale / 2
  view.value.y =
    scale > height ? Math.max(height / 2, Math.min(scale - height / 2, view.value.y)) : scale / 2
}

function applyLimits() {
  const { width, height } = frame.value
  if (width === 0 || height === 0) return
  holdZoomAboveTheFrame(width, height)
  holdInsideTheWorld(width, height)
}

function measure() {
  if (mapElement.value === null) return
  frame.value = { width: mapElement.value.clientWidth, height: mapElement.value.clientHeight }
  applyLimits()
}

function centreOn(latitude, longitude, zoom) {
  view.value = {
    x: worldXFromLongitude(longitude, zoom),
    y: worldYFromLatitude(latitude, zoom),
    zoom,
  }
  applyLimits()
}

function placeAt(clientX, clientY) {
  const latitude = latitudeFromWorldY(origin.value.top + frameY(clientY), view.value.zoom)
  const longitude = longitudeFromWorldX(origin.value.left + frameX(clientX), view.value.zoom)
  placed = { latitude: rounded(latitude), longitude: rounded(longitude) }
  emit('place', placed)
}

// Zooms about a point in the frame, the centre when none is given. Whatever is under that
// point stays under it, which is what makes a double click land where it was aimed rather
// than dragging the map out from under the pointer.
function zoomBy(step, anchorX, anchorY) {
  const { width, height } = frame.value
  const zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, view.value.zoom + step))
  if (zoom === view.value.zoom) return
  const x = anchorX ?? width / 2
  const y = anchorY ?? height / 2
  const factor = 2 ** (zoom - view.value.zoom)
  const worldX = view.value.x - width / 2 + x
  const worldY = view.value.y - height / 2 + y
  view.value = {
    x: worldX * factor + width / 2 - x,
    y: worldY * factor + height / 2 - y,
    zoom,
  }
  applyLimits()
}

function toggleExpanded() {
  expanded.value = !expanded.value
  // The frame changes size, which the resize observer picks up before the next paint.
}

function useMyLocation() {
  navigator.geolocation.getCurrentPosition((position) => {
    placed = {
      latitude: rounded(position.coords.latitude),
      longitude: rounded(position.coords.longitude),
    }
    emit('place', placed)
    centreOn(placed.latitude, placed.longitude, PLACE_ZOOM)
  })
}

function frameX(clientX) {
  const rectangle = mapElement.value.getBoundingClientRect()
  return clientX - rectangle.left - mapElement.value.clientLeft
}

function frameY(clientY) {
  const rectangle = mapElement.value.getBoundingClientRect()
  return clientY - rectangle.top - mapElement.value.clientTop
}

function pointerList() {
  return Object.values(pointers)
}

function spread(points) {
  return Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y)
}

function midpoint(points) {
  return {
    x: frameX((points[0].x + points[1].x) / 2),
    y: frameY((points[0].y + points[1].y) / 2),
  }
}

// A pinch is shown by scaling the tiles that are already there and committed to a whole
// zoom level when the fingers lift. Redrawing at a fraction of a level would mean tiles at
// one zoom stretched to another, which is what the scale here is doing anyway, only
// without pretending it is a new map.
function startPinch() {
  const points = pointerList()
  const centre = midpoint(points)
  pinch.value = { spread: spread(points), x: centre.x, y: centre.y, scale: 1 }
  drag = null
  ignoreNextPress = true
}

function updatePinch() {
  const points = pointerList()
  if (pinch.value === null || points.length < 2) return
  const centre = midpoint(points)
  pinch.value = {
    spread: pinch.value.spread,
    x: centre.x,
    y: centre.y,
    scale: spread(points) / pinch.value.spread,
  }
}

function endPinch() {
  if (pinch.value === null) return
  const { scale, x, y } = pinch.value
  pinch.value = null
  zoomBy(Math.round(Math.log2(scale)), x, y)
}

function onPointerDown(event) {
  // The controls sit on top of the map and are not places.
  if (event.target.closest('.map-zoom, .map-credit')) return
  pointers[event.pointerId] = { x: event.clientX, y: event.clientY }
  const count = pointerList().length
  if (count === 2) {
    startPinch()
    return
  }
  if (count > 2) return
  // Capturing keeps a drag alive when the pointer leaves the map. It is an improvement,
  // not a requirement, so a browser that refuses still pans.
  try {
    mapElement.value.setPointerCapture(event.pointerId)
  } catch {
    // Nothing to do: the drag below works either way.
  }
  drag = { x: event.clientX, y: event.clientY, moved: 0 }
}

function onPointerMove(event) {
  if (!(event.pointerId in pointers)) return
  const previous = pointers[event.pointerId]
  pointers[event.pointerId] = { x: event.clientX, y: event.clientY }

  if (pinch.value !== null) {
    updatePinch()
    return
  }
  if (drag === null) return

  const movedX = event.clientX - previous.x
  const movedY = event.clientY - previous.y
  drag.moved += Math.abs(movedX) + Math.abs(movedY)
  view.value.x -= movedX
  view.value.y -= movedY
  applyLimits()
}

function onPointerRelease(event) {
  if (!(event.pointerId in pointers)) return
  delete pointers[event.pointerId]

  if (pinch.value !== null && pointerList().length < 2) endPinch()
  if (pointerList().length > 0) return

  const wasAPress = drag !== null && drag.moved < DRAG_SLOP_PX && !ignoreNextPress
  drag = null
  ignoreNextPress = false
  if (wasAPress) placeAt(event.clientX, event.clientY)
}

function onDoubleClick(event) {
  zoomBy(1, frameX(event.clientX), frameY(event.clientY))
}

function onWheel(event) {
  // A trackpad pinch arrives as ctrl and a wheel, which is a zoom wherever it lands.
  // Plain scrolling only zooms once the map is expanded, so a small map sitting in the
  // middle of a form never swallows the page scroll of somebody trying to reach the
  // fields below it.
  if (!event.ctrlKey && !expanded.value) return
  event.preventDefault()
  if (wheelSoFar * event.deltaY < 0) wheelSoFar = 0
  wheelSoFar += event.deltaY
  if (Math.abs(wheelSoFar) < WHEEL_PER_ZOOM) return
  const step = wheelSoFar < 0 ? 1 : -1
  wheelSoFar = 0
  zoomBy(step, frameX(event.clientX), frameY(event.clientY))
}

function onKeyDown(event) {
  if (event.key === 'Escape' && expanded.value) toggleExpanded()
}

// Typing recentres but does not zoom, once there is a pin to move: somebody who zoomed out
// to look around and then corrected a digit meant to stay where they were. A click on the
// map moves the pin only, since the point it named is already on screen.
watch(
  point,
  (current, previous) => {
    if (current === null) return
    if (
      placed !== null &&
      placed.latitude === current.latitude &&
      placed.longitude === current.longitude
    ) {
      return
    }
    centreOn(current.latitude, current.longitude, previous ? view.value.zoom : PLACE_ZOOM)
  },
  { immediate: true },
)

onMounted(() => {
  resizeObserver = new ResizeObserver(measure)
  resizeObserver.observe(mapElement.value)
  measure()
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<style scoped>
.map-hint {
  font-size: 0.8125rem;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 0.75rem;
}

.map {
  position: relative;
  height: 240px;
  border-radius: 8px;
  border: 1px solid var(--admin-card-border);
  background-color: var(--admin-input-bg);
  overflow: hidden;
  cursor: crosshair;
  /* The map handles its own dragging, so the browser must not scroll the page instead. */
  touch-action: none;
}

.map-tiles {
  position: absolute;
  inset: 0;
}

.map-tile {
  position: absolute;
  width: 256px;
  height: 256px;
  user-select: none;
}

.map-pin {
  position: absolute;
  width: 14px;
  height: 14px;
  margin: -7px 0 0 -7px;
  border-radius: 50%;
  border: 2px solid #fff;
  background-color: var(--admin-accent);
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.5);
  pointer-events: none;
}

/* Big enough to pick a rooftop on. Fixed rather than sized to the card, so it covers the
   form instead of pushing it around, and Escape or the button puts it back. */
.map.is-expanded {
  position: fixed;
  inset: 1rem;
  height: auto;
  z-index: 1060;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.map-zoom {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  display: grid;
  gap: 0.25rem;
}

.map-button {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background-color: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 0.8rem;
  line-height: 1;
  padding: 0;
  cursor: pointer;
}

.map-button:hover {
  background-color: rgba(0, 0, 0, 0.75);
}

.map-credit {
  position: absolute;
  right: 0;
  bottom: 0;
  margin: 0;
  padding: 0.1rem 0.4rem;
  border-radius: 6px 0 0 0;
  background-color: rgba(0, 0, 0, 0.55);
  font-size: 0.65rem;
}

.map-credit a {
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
}

.map-offline {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}

.map-locate {
  margin-top: 0.75rem;
}
</style>
