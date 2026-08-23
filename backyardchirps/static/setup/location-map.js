// The location step's map. Click it to set the coordinates, and typing coordinates moves
// the pin, so the fields and the map always show the same point.
//
// Written out rather than pulled from a tile library, because a picker needs only the
// Web Mercator projection, a grid of images and a drag handler. The tiles come from
// OpenStreetMap, so a station with no internet during setup shows an empty frame and a
// note, and the two fields still work on their own.
//
// The settings page shows the same picker, as
// frontend/src/components/settings/LocationMapPicker.vue. It is a second copy rather than
// a shared module, because this file is served by Django to a page the Vue app does not
// build, so a change here usually belongs there too.
;(function () {
  var TILE_SIZE = 256
  var MIN_ZOOM = 2
  var MAX_ZOOM = 16
  // Close enough to tell one garden from the next, which is the scale this question is
  // asked at.
  var PLACE_ZOOM = 13
  // Where a station with no coordinates starts: the whole world, so the first click can
  // land anywhere.
  var START_LAT = 25
  var START_LON = 0
  // Web Mercator cannot draw the poles, so latitude stops where the square world does.
  var MAX_LATITUDE = 85.05112878
  // A press that moves less than this is somebody pointing at a place, not dragging.
  var DRAG_SLOP_PX = 4
  // How much wheel a zoom level costs. A mouse notch is around 100 and a trackpad sends
  // a stream of small ones, so this collects them rather than jumping a level each time.
  var WHEEL_PER_ZOOM = 50

  var map = document.getElementById('location-map')
  if (!map) return

  var tileLayer = document.getElementById('map-tiles')
  var pinElement = document.getElementById('map-pin')
  var offlineNote = document.getElementById('map-offline')
  var latitudeInput = document.getElementById('location_lat')
  var longitudeInput = document.getElementById('location_lon')

  // The tiles on screen, keyed by zoom/x/y, so panning reuses what is already loaded and
  // only the tiles that scrolled out are thrown away.
  var tiles = {}
  // The centre, held as world pixels at the current zoom rather than as coordinates:
  // panning is then a subtraction and zooming a multiplication.
  var view = { x: 0, y: 0, zoom: MIN_ZOOM }
  var pin = null
  var drag = null
  // Every finger or pen currently down, by pointer id. One is a drag, two are a pinch.
  var pointers = {}
  var pinch = null
  // A pinch ends with fingers lifting one at a time, and neither lift is somebody
  // pointing at a place.
  var ignoreNextPress = false
  var wheelSoFar = 0

  function scaleAt(zoom) {
    return TILE_SIZE * Math.pow(2, zoom)
  }

  function worldXFromLon(lon, zoom) {
    return ((lon + 180) / 360) * scaleAt(zoom)
  }

  function worldYFromLat(lat, zoom) {
    var bounded = Math.max(-MAX_LATITUDE, Math.min(MAX_LATITUDE, lat))
    var sine = Math.sin((bounded * Math.PI) / 180)
    return (0.5 - Math.log((1 + sine) / (1 - sine)) / (4 * Math.PI)) * scaleAt(zoom)
  }

  function lonFromWorldX(x, zoom) {
    return (x / scaleAt(zoom)) * 360 - 180
  }

  function latFromWorldY(y, zoom) {
    var projected = Math.PI - (2 * Math.PI * y) / scaleAt(zoom)
    return (180 / Math.PI) * Math.atan(Math.sinh(projected))
  }

  function centreOn(lat, lon, zoom) {
    view = { x: worldXFromLon(lon, zoom), y: worldYFromLat(lat, zoom), zoom: zoom }
  }

  function isExpanded() {
    return map.classList.contains('is-expanded')
  }

  // The world has to be at least as big as the frame it is drawn in, or the map would sit
  // in a letterbox. The small map never reaches this; the expanded one does.
  function holdZoomAboveTheFrame(width, height) {
    var needed = Math.ceil(Math.log2(Math.max(width, height) / TILE_SIZE))
    var lowest = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, needed))
    if (view.zoom >= lowest) return
    var factor = Math.pow(2, lowest - view.zoom)
    view = { x: view.x * factor, y: view.y * factor, zoom: lowest }
  }

  // Keep the world inside the frame, so there is no way to drag off the edge into grey.
  function holdInsideTheWorld(width, height) {
    var scale = scaleAt(view.zoom)
    view.x = scale > width ? Math.max(width / 2, Math.min(scale - width / 2, view.x)) : scale / 2
    view.y = scale > height ? Math.max(height / 2, Math.min(scale - height / 2, view.y)) : scale / 2
  }

  function render() {
    var width = map.clientWidth
    var height = map.clientHeight
    holdZoomAboveTheFrame(width, height)
    holdInsideTheWorld(width, height)
    // Rounded, so a tile never lands on half a pixel and gets resampled for nothing.
    var left = Math.round(view.x - width / 2)
    var top = Math.round(view.y - height / 2)
    renderTiles(left, top, width, height)
    renderPin(left, top, width, height)
  }

  function renderTiles(left, top, width, height) {
    var lastIndex = Math.pow(2, view.zoom) - 1
    var firstX = Math.max(0, Math.floor(left / TILE_SIZE))
    var firstY = Math.max(0, Math.floor(top / TILE_SIZE))
    var lastX = Math.min(lastIndex, Math.floor((left + width) / TILE_SIZE))
    var lastY = Math.min(lastIndex, Math.floor((top + height) / TILE_SIZE))
    var wanted = {}

    for (var tileY = firstY; tileY <= lastY; tileY++) {
      for (var tileX = firstX; tileX <= lastX; tileX++) {
        var key = view.zoom + '/' + tileX + '/' + tileY
        var tile = tiles[key] || addTile(key, tileX, tileY)
        tile.style.left = tileX * TILE_SIZE - left + 'px'
        tile.style.top = tileY * TILE_SIZE - top + 'px'
        wanted[key] = true
      }
    }

    Object.keys(tiles).forEach(function (key) {
      if (wanted[key]) return
      tileLayer.removeChild(tiles[key])
      delete tiles[key]
    })
  }

  function addTile(key, tileX, tileY) {
    var tile = document.createElement('img')
    tile.className = 'map-tile'
    tile.alt = ''
    tile.draggable = false
    tile.addEventListener('error', showOfflineNote)
    tile.src = 'https://tile.openstreetmap.org/' + view.zoom + '/' + tileX + '/' + tileY + '.png'
    tileLayer.appendChild(tile)
    tiles[key] = tile
    return tile
  }

  function renderPin(left, top, width, height) {
    if (pin === null) {
      pinElement.hidden = true
      return
    }
    var x = worldXFromLon(pin.lon, view.zoom) - left
    var y = worldYFromLat(pin.lat, view.zoom) - top
    pinElement.hidden = x < 0 || y < 0 || x > width || y > height
    pinElement.style.left = x + 'px'
    pinElement.style.top = y + 'px'
  }

  function showOfflineNote() {
    offlineNote.hidden = false
  }

  function readInputs() {
    var lat = parseFloat(latitudeInput.value)
    var lon = parseFloat(longitudeInput.value)
    if (isNaN(lat) || isNaN(lon)) return null
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null
    return { lat: lat, lon: lon }
  }

  function writeInputs(lat, lon) {
    // Five decimals is about a metre, which is as much as anyone can point at on a map
    // and more than the species list needs.
    latitudeInput.value = lat.toFixed(5)
    longitudeInput.value = lon.toFixed(5)
  }

  function moveTo(lat, lon, zoom) {
    pin = { lat: lat, lon: lon }
    centreOn(lat, lon, zoom)
    render()
  }

  // Typing recentres but does not zoom, once there is a pin to move: somebody who zoomed
  // out to look around and then corrected a digit meant to stay where they were.
  function followInputs() {
    var typed = readInputs()
    if (typed === null) return
    moveTo(typed.lat, typed.lon, pin === null ? PLACE_ZOOM : view.zoom)
  }

  function placeAt(clientX, clientY) {
    var frame = map.getBoundingClientRect()
    var left = view.x - frame.width / 2
    var top = view.y - frame.height / 2
    var lat = latFromWorldY(top + (clientY - frame.top), view.zoom)
    var lon = lonFromWorldX(left + (clientX - frame.left), view.zoom)
    writeInputs(lat, lon)
    pin = { lat: lat, lon: lon }
    render()
  }

  // Zooms about a point in the frame, the centre when none is given. Whatever is under
  // that point stays under it, which is what makes a double click land where it was aimed
  // rather than dragging the map out from under the pointer.
  function zoomBy(step, anchorX, anchorY) {
    var width = map.clientWidth
    var height = map.clientHeight
    var zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, view.zoom + step))
    if (zoom === view.zoom) return
    var x = anchorX === undefined ? width / 2 : anchorX
    var y = anchorY === undefined ? height / 2 : anchorY
    var factor = Math.pow(2, zoom - view.zoom)
    var worldX = view.x - width / 2 + x
    var worldY = view.y - height / 2 + y
    view = { x: worldX * factor + width / 2 - x, y: worldY * factor + height / 2 - y, zoom: zoom }
    render()
  }

  function frameX(clientX) {
    return clientX - map.getBoundingClientRect().left
  }

  function frameY(clientY) {
    return clientY - map.getBoundingClientRect().top
  }

  function pointerList() {
    return Object.keys(pointers).map(function (id) {
      return pointers[id]
    })
  }

  function spread(points) {
    return Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y)
  }

  function midpoint(points) {
    return {
      x: frameX((points[0].x + points[1].x) / 2),
      y: frameY((points[0].y + points[1].y) / 2)
    }
  }

  // A pinch is shown by scaling the tiles that are already there and committed to a whole
  // zoom level when the fingers lift. Redrawing at a fraction of a level would mean tiles
  // at one zoom stretched to another, which is what the scale here is doing anyway, only
  // without pretending it is a new map.
  function startPinch() {
    var points = pointerList()
    var centre = midpoint(points)
    pinch = { spread: spread(points), x: centre.x, y: centre.y, scale: 1 }
    drag = null
    ignoreNextPress = true
    pinElement.hidden = true
  }

  function updatePinch() {
    var points = pointerList()
    if (pinch === null || points.length < 2) return
    var centre = midpoint(points)
    pinch.scale = spread(points) / pinch.spread
    pinch.x = centre.x
    pinch.y = centre.y
    tileLayer.style.transformOrigin = pinch.x + 'px ' + pinch.y + 'px'
    tileLayer.style.transform = 'scale(' + pinch.scale + ')'
  }

  function endPinch() {
    if (pinch === null) return
    var scale = pinch.scale
    var x = pinch.x
    var y = pinch.y
    pinch = null
    tileLayer.style.transform = ''
    tileLayer.style.transformOrigin = ''
    zoomBy(Math.round(Math.log2(scale)), x, y)
    render()
  }

  function toggleExpanded() {
    map.classList.toggle('is-expanded')
    // Reading the frame back flushes the layout, so this draws for the new size rather
    // than the old one.
    render()
  }

  map.addEventListener('pointerdown', function (event) {
    // The controls sit on top of the map and are not places.
    if (event.target.closest('.map-zoom, .map-credit')) return
    pointers[event.pointerId] = { x: event.clientX, y: event.clientY }
    var count = pointerList().length
    if (count === 2) {
      startPinch()
      return
    }
    if (count > 2) return
    // Capturing keeps a drag alive when the pointer leaves the map. It is an
    // improvement, not a requirement, so a browser that refuses still pans.
    try {
      map.setPointerCapture(event.pointerId)
    } catch (ignored) {
      // Nothing to do: the drag below works either way.
    }
    drag = { x: event.clientX, y: event.clientY, moved: 0 }
  })

  map.addEventListener('pointermove', function (event) {
    if (!(event.pointerId in pointers)) return
    var previous = pointers[event.pointerId]
    pointers[event.pointerId] = { x: event.clientX, y: event.clientY }

    if (pinch !== null) {
      updatePinch()
      return
    }
    if (drag === null) return

    var movedX = event.clientX - previous.x
    var movedY = event.clientY - previous.y
    drag.moved += Math.abs(movedX) + Math.abs(movedY)
    view.x -= movedX
    view.y -= movedY
    render()
  })

  function releasePointer(event) {
    if (!(event.pointerId in pointers)) return
    delete pointers[event.pointerId]

    if (pinch !== null && pointerList().length < 2) endPinch()
    if (pointerList().length > 0) return

    var wasAPress = drag !== null && drag.moved < DRAG_SLOP_PX && !ignoreNextPress
    drag = null
    ignoreNextPress = false
    if (wasAPress) placeAt(event.clientX, event.clientY)
  }

  map.addEventListener('pointerup', releasePointer)
  map.addEventListener('pointercancel', releasePointer)

  map.addEventListener('dblclick', function (event) {
    zoomBy(1, frameX(event.clientX), frameY(event.clientY))
  })

  map.addEventListener(
    'wheel',
    function (event) {
      // A trackpad pinch arrives as ctrl and a wheel, which is a zoom wherever it lands.
      // Plain scrolling only zooms once the map is expanded, so a small map sitting in the
      // middle of a form never swallows the page scroll of somebody trying to reach the
      // fields below it.
      if (!event.ctrlKey && !isExpanded()) return
      event.preventDefault()
      if (wheelSoFar * event.deltaY < 0) wheelSoFar = 0
      wheelSoFar += event.deltaY
      if (Math.abs(wheelSoFar) < WHEEL_PER_ZOOM) return
      var step = wheelSoFar < 0 ? 1 : -1
      wheelSoFar = 0
      zoomBy(step, frameX(event.clientX), frameY(event.clientY))
    },
    { passive: false }
  )

  document.getElementById('map-zoom-in').addEventListener('click', function () {
    zoomBy(1)
  })

  document.getElementById('map-zoom-out').addEventListener('click', function () {
    zoomBy(-1)
  })

  document.getElementById('map-expand').addEventListener('click', toggleExpanded)
  document.getElementById('map-collapse').addEventListener('click', toggleExpanded)

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && isExpanded()) toggleExpanded()
  })

  document.getElementById('use-my-location').addEventListener('click', function () {
    navigator.geolocation.getCurrentPosition(function (position) {
      writeInputs(position.coords.latitude, position.coords.longitude)
      moveTo(position.coords.latitude, position.coords.longitude, PLACE_ZOOM)
    })
  })

  latitudeInput.addEventListener('input', followInputs)
  longitudeInput.addEventListener('input', followInputs)
  window.addEventListener('resize', render)

  var saved = readInputs()
  if (saved === null) {
    centreOn(START_LAT, START_LON, MIN_ZOOM)
    render()
  } else {
    moveTo(saved.lat, saved.lon, PLACE_ZOOM)
  }
})()
