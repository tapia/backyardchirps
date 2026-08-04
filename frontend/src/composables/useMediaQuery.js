import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Reactive `matchMedia`: returns a ref that tracks whether the given media
 * query currently matches, updating as the viewport changes. Used to switch
 * component structure (not just styling) between mobile and desktop.
 */
export function useMediaQuery(query) {
  const matches = ref(false)
  let mediaQueryList = null

  function update(event) {
    matches.value = event.matches
  }

  onMounted(() => {
    mediaQueryList = window.matchMedia(query)
    matches.value = mediaQueryList.matches
    mediaQueryList.addEventListener('change', update)
  })

  onUnmounted(() => {
    mediaQueryList?.removeEventListener('change', update)
  })

  return matches
}
