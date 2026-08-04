import { ref } from 'vue'

const COPIED_LABEL_DURATION_MS = 1500

/**
 * Copies a shareable URL to the clipboard and exposes a brief "copied"
 * acknowledgement state for the calling component to render.
 */
export function useShare() {
  const shareCopied = ref(false)
  let shareCopiedTimer = null

  async function share(url) {
    try {
      await navigator.clipboard.writeText(url)
      shareCopied.value = true
      clearTimeout(shareCopiedTimer)
      shareCopiedTimer = setTimeout(() => {
        shareCopied.value = false
      }, COPIED_LABEL_DURATION_MS)
    } catch {
      // Clipboard access denied; nothing to do.
    }
  }

  return { shareCopied, share }
}
