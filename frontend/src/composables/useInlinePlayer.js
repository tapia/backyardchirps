import { ref } from 'vue'

// Coordinates a list of <InlineAudioRow> so only one row is expanded/playing at
// a time. The active row is tracked by its URL; a row stops itself when it is
// no longer the active one.
export function useInlinePlayer() {
  const activeUrl = ref(null)

  function isActive(url) {
    return activeUrl.value === url
  }

  function activate(url) {
    activeUrl.value = url
  }

  function deactivate() {
    activeUrl.value = null
  }

  function reset() {
    activeUrl.value = null
  }

  return { activeUrl, isActive, activate, deactivate, reset }
}
