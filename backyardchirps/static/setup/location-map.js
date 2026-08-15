// The location step's map. Click it to set the coordinates, and typing coordinates moves
// the pin, so the fields and the map always show the same point.
//
// Written out rather than pulled from a tile library, because a picker needs only the
// Web Mercator projection, a grid of images and a drag handler. The tiles come from
// OpenStreetMap, so a station with no internet during setup shows an empty frame and a
// note, and the two fields still work on their own.
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

  // Keep the world inside the frame, so there is no way to drag off the edge into grey.
  function holdInsideTheWorld(width, height) {
    var scale = scaleAt(view.zoom)
    view.x = scale > width ? Math.max(width / 2, Math.min(scale - width / 2, view.x)) : scale / 2
    view.y = scale > height ? Math.max(height / 2, Math.min(scale - height / 2, view.y)) : scale / 2
  }

  function render() {
    var width = map.clientWidth
    var height = map.clientHeight
    holdInsideTheWorld(width, height)
    var left = view.x - width / 2
    var top = view.y - height / 2
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

  function placeAt(event) {
    var frame = map.getBoundingClientRect()
    var left = view.x - frame.width / 2
    var top = view.y - frame.height / 2
    var lat = latFromWorldY(top + (event.clientY - frame.top), view.zoom)
    var lon = lonFromWorldX(left + (event.clientX - frame.left), view.zoom)
    writeInputs(lat, lon)
    pin = { lat: lat, lon: lon }
    render()
  }

  function zoomBy(step) {
    var zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, view.zoom + step))
    if (zoom === view.zoom) return
    var factor = Math.pow(2, zoom - view.zoom)
    // Scaling the centre keeps the same place in the middle of the frame.
    view = { x: view.x * factor, y: view.y * factor, zoom: zoom }
    render()
  }

  map.addEventListener('pointerdown', function (event) {
    // The zoom buttons and the credit sit on top of the map and are not places.
    if (event.target !== map && event.target.className !== 'map-tile') return
    map.setPointerCapture(event.pointerId)
    drag = { x: event.clientX, y: event.clientY, moved: 0 }
  })

  map.addEventListener('pointermove', function (event) {
    if (drag === null) return
    var movedX = event.clientX - drag.x
    var movedY = event.clientY - drag.y
    drag.x = event.clientX
    drag.y = event.clientY
    drag.moved += Math.abs(movedX) + Math.abs(movedY)
    view.x -= movedX
    view.y -= movedY
    render()
  })

  map.addEventListener('pointerup', function (event) {
    if (drag === null) return
    var wasAPress = drag.moved < DRAG_SLOP_PX
    drag = null
    if (wasAPress) placeAt(event)
  })

  map.addEventListener('pointercancel', function () {
    drag = null
  })

  document.getElementById('map-zoom-in').addEventListener('click', function () {
    zoomBy(1)
  })

  document.getElementById('map-zoom-out').addEventListener('click', function () {
    zoomBy(-1)
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
