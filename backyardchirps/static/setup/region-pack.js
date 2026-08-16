// The region pack step. Starts the download and then asks how it is going.
//
// The download does not happen in this page's request, so closing the tab or letting a
// phone lock its screen does not stop it. Coming back to this step picks the same install
// up again, because the answer comes from a file on the station rather than from anything
// this script remembers.
;(function () {
  var step = document.getElementById('region-pack')
  if (!step) return

  var button = document.getElementById('region-pack-install')
  var meter = document.getElementById('region-pack-meter')
  var fill = document.getElementById('region-pack-fill')
  var notes = {
    running: document.getElementById('region-pack-working'),
    done: document.getElementById('region-pack-done'),
    failed: document.getElementById('region-pack-failed'),
  }

  // How often to ask. A region pack takes minutes, so a second is often enough for a bar that
  // moves smoothly and rare enough to cost the station nothing.
  var POLL_MS = 1000

  var polling = null

  function show(state) {
    Object.keys(notes).forEach(function (name) {
      notes[name].hidden = name !== state
    })
    meter.hidden = state !== 'running'
    button.hidden = state === 'running' || state === 'done'
  }

  function draw(progress) {
    // A width is a runtime-computed number with no name, so it is set directly. Which
    // state the step is in has names, and those are the paragraphs above.
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

  function startPolling() {
    stopPolling()
    polling = window.setInterval(poll, POLL_MS)
  }

  function csrfToken() {
    // CSRF_USE_SESSIONS is on, so there is no cookie to read. The token is the hidden
    // field Django rendered into the step's own form.
    var field = document.querySelector('input[name=csrfmiddlewaretoken]')
    return field ? field.value : ''
  }

  button.addEventListener('click', function () {
    show('running')
    fill.style.width = '0'
    window
      .fetch('/api/region-packs/install/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify({ id: step.dataset.regionPackId }),
      })
      .then(function (response) {
        // 409 means one was already running, which is not an error: watch that one.
        if (!response.ok && response.status !== 409) throw new Error('refused')
        startPolling()
      })
      .catch(function () {
        show('failed')
      })
  })

  // An install already under way when this page opens, which is what coming back to the
  // step looks like.
  window
    .fetch('/api/region-packs/install/progress/', { credentials: 'same-origin' })
    .then(function (response) {
      return response.ok ? response.json() : null
    })
    .then(function (progress) {
      if (apply(progress)) startPolling()
    })
    .catch(function () {})
})()
