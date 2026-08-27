// How far the region pack download has got, on the last step of the wizard.
//
// The download does not happen in this page's request, so closing the tab or letting a
// phone lock its screen does not stop it, and neither does pressing Finish. The answer
// comes from a file on the station rather than from anything this script remembers, so
// coming back to the step picks the same download up again.
;(function () {
  var step = document.getElementById('region-pack-progress')
  if (!step) return

  var meter = document.getElementById('region-pack-meter')
  var fill = document.getElementById('region-pack-fill')
  var notes = {
    running: document.getElementById('region-pack-working'),
    done: document.getElementById('region-pack-done'),
    failed: document.getElementById('region-pack-failed'),
  }

  // How often to ask. A region pack takes minutes, so a second is often enough for a bar
  // that moves smoothly and rare enough to cost the station nothing.
  var POLL_MS = 1000

  var polling = null

  function show(state) {
    Object.keys(notes).forEach(function (name) {
      notes[name].hidden = name !== state
    })
    meter.hidden = state !== 'running'
  }

  function draw(progress) {
    // A width is a runtime-computed number with no name, so it is set directly. Which
    // state the download is in has names, and those are the paragraphs above.
    if (progress.fraction === null || progress.fraction === undefined) return
    fill.style.width = Math.round(progress.fraction * 100) + '%'
  }

  function stopPolling() {
    if (polling !== null) {
      window.clearInterval(polling)
      polling = null
    }
  }

  function apply(progress) {
    if (!progress || !progress.state) return false
    show(progress.state)
    draw(progress)
    if (progress.state !== 'running') {
      stopPolling()
      return false
    }
    return true
  }

  function poll() {
    window
      .fetch('/api/region-packs/install/progress/', { credentials: 'same-origin' })
      .then(function (response) {
        return response.ok ? response.json() : null
      })
      .then(apply)
      .catch(function () {
        // A single failed poll says nothing about the download, which is running on the
        // station rather than here. Keep asking.
      })
  }

  poll()
  polling = window.setInterval(poll, POLL_MS)
})()
