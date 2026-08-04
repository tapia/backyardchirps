import { ref } from 'vue'

// State and event handlers for one <audio> element. The component owning the
// element binds audioEl as its ref and wires the on* handlers to the matching
// DOM events. Supports a single fixed source (toggle) or switching between
// several clips sharing the element (toggleUrl + currentUrl).
export function useAudioPlayer() {
  const audioEl = ref(null)
  const playing = ref(false)
  const progressPct = ref(0)
  const duration = ref(0)
  const currentTime = ref(0)
  const seekingForDuration = ref(false)
  const currentUrl = ref(null)

  function prepareForNewSrc() {
    progressPct.value = 0
    duration.value = 0
    currentTime.value = 0
    seekingForDuration.value = false
  }

  function onLoadedMetadata() {
    // Streamed clips can report an infinite duration until the browser has
    // seen the end of the file; seeking far past the end forces it to resolve.
    const element = audioEl.value
    if (element && !isFinite(element.duration)) {
      seekingForDuration.value = true
      element.currentTime = 1e10
    }
  }

  function onDurationChange() {
    const element = audioEl.value
    if (!element) return
    const loadedDuration = element.duration
    if (loadedDuration && isFinite(loadedDuration)) {
      duration.value = loadedDuration
      if (seekingForDuration.value) {
        seekingForDuration.value = false
        element.currentTime = 0
      }
    }
  }

  function onTimeUpdate() {
    if (!seekingForDuration.value && duration.value > 0) {
      currentTime.value = audioEl.value.currentTime
      progressPct.value = (audioEl.value.currentTime / duration.value) * 100
    }
  }

  function onEnded() {
    playing.value = false
    progressPct.value = 0
    currentTime.value = 0
    if (audioEl.value) audioEl.value.currentTime = 0
  }

  function toggle() {
    if (!audioEl.value) return
    playing.value ? audioEl.value.pause() : audioEl.value.play()
  }

  function toggleUrl(url) {
    if (currentUrl.value === url) {
      toggle()
    } else {
      currentUrl.value = url
      prepareForNewSrc()
      audioEl.value.src = url
      audioEl.value.play()
    }
  }

  function reset() {
    audioEl.value?.pause()
    if (audioEl.value) audioEl.value.src = ''
    playing.value = false
    progressPct.value = 0
    duration.value = 0
    currentTime.value = 0
    seekingForDuration.value = false
    currentUrl.value = null
  }

  return {
    audioEl,
    playing,
    progressPct,
    duration,
    currentTime,
    currentUrl,
    onLoadedMetadata,
    onDurationChange,
    onTimeUpdate,
    onEnded,
    toggle,
    toggleUrl,
    reset,
  }
}
