// The microphone step's level meter. The only part of the wizard a page reload cannot
// do, so it holds a stream of readings open and moves a bar.
//
// The stream replaced a poll that opened the device once per request. That left the
// microphone shut between readings, so a clap could land in a gap and never show, and on
// a Pi 3 a round trip outlasted the interval, which put two readings on the device at
// once and made one of them fail as busy. Both looked like a broken microphone.
;(function () {
  var fill = document.getElementById('meter-fill')
  if (!fill) return

  var notes = {
    device_busy: document.getElementById('meter-busy'),
    unopenable: document.getElementById('meter-unopenable'),
    clipping: document.getElementById('meter-clipping'),
  }

  // Where the bar starts, in dBFS. A quiet room reads around -60 on a USB microphone and
  // speech at arm's length peaks near -20, so drawing the raw 0-to-1 sample value would
  // leave a working microphone with a bar a few pixels wide.
  var FLOOR_DB = -60
  // How far the bar falls per reading when the sound stops. A peak lasts one reading and
  // the next is silence again, so without this the bar flickers instead of dropping.
  var DECAY = 0.08
  // A sample this close to the top is hitting the ceiling, and what the microphone
  // records is being cut off rather than recorded quietly.
  var CLIPPING = 0.99
  // How long to wait before trying a device that would not open. Long enough that a busy
  // microphone is not asked twice a second, short enough that stopping whatever holds it
  // shows up while the user is still watching.
  var REOPEN_MS = 3000

  var shown = 0
  var source = null
  var reopen = null

  function selectedDevice() {
    var checked = document.querySelector('input[name="audio_device"]:checked')
    return checked ? checked.value : ''
  }

  function show(name) {
    for (var key in notes) {
      if (notes[key]) notes[key].hidden = key !== name
    }
  }

  function scaled(peak) {
    if (peak <= 0) return 0
    var decibels = 20 * Math.log10(peak)
    if (decibels <= FLOOR_DB) return 0
    return Math.min(1, (decibels - FLOOR_DB) / -FLOOR_DB)
  }

  function draw(peak) {
    shown = Math.max(scaled(peak), shown - DECAY)
    fill.style.width = Math.round(shown * 100) + '%'
    fill.classList.toggle('clipping', peak >= CLIPPING)
  }

  function reset() {
    shown = 0
    fill.style.width = '0'
    fill.classList.remove('clipping')
  }

  function onReading(event) {
    var reading = JSON.parse(event.data)
    if (reading.error) {
      show(notes[reading.error] ? reading.error : 'unopenable')
      reset()
      // The stream is over once it says this, and the browser would reopen it in half a
      // second. Take it over so a device held by something else is asked at a human pace.
      stop()
      reopen = window.setTimeout(listen, REOPEN_MS)
      return
    }
    show(reading.peak >= CLIPPING ? 'clipping' : null)
    draw(reading.peak)
  }

  function stop() {
    if (source) source.close()
    source = null
    window.clearTimeout(reopen)
  }

  function listen() {
    stop()
    reset()
    var device = selectedDevice()
    source = new EventSource('/setup/audio-level/' + (device === '' ? '' : '?device=' + encodeURIComponent(device)))
    source.onmessage = onReading
  }

  var choices = document.querySelectorAll('input[name="audio_device"]')
  for (var index = 0; index < choices.length; index++) {
    choices[index].addEventListener('change', listen)
  }
  // Leaving the step has to hand the microphone back, and the next step may be the one
  // that starts the recorder.
  window.addEventListener('pagehide', stop)
  listen()
})()
