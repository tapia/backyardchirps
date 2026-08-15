// The microphone step's level meter. The only part of the wizard a page reload cannot
// do, so it polls a small JSON view and moves a bar.
;(function () {
  var fill = document.getElementById('meter-fill')
  var note = document.getElementById('meter-note')
  if (!fill) return

  function selectedDevice() {
    var checked = document.querySelector('input[name="audio_device"]:checked')
    return checked ? checked.value : ''
  }

  function poll() {
    var device = selectedDevice()
    var url = '/setup/audio-level/' + (device === '' ? '' : '?device=' + encodeURIComponent(device))
    fetch(url)
      .then(function (response) {
        return response.json().then(function (body) {
          return { ok: response.ok, body: body }
        })
      })
      .then(function (result) {
        if (!result.ok) {
          note.textContent =
            result.body.error === 'device_busy'
              ? 'The microphone is in use by something else.'
              : 'That device could not be opened.'
          fill.style.width = '0'
          return
        }
        note.textContent = ''
        fill.style.width = Math.min(100, Math.round(result.body.peak * 100)) + '%'
      })
      .catch(function () {
        note.textContent = ''
      })
  }

  setInterval(poll, 1000)
  poll()
})()
