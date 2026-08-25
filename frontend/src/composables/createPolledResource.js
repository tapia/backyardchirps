import { ref } from 'vue'

// Builds a composable around data that is re-fetched on a fixed interval.
// Polling runs while at least one component has called start() without a
// matching stop(), so several consumers share a single timer.
export function createPolledResource(fetchResource, intervalMs) {
  const data = ref(null)
  let intervalId = null
  let consumerCount = 0

  async function refresh() {
    try {
      data.value = await fetchResource()
    } catch {
      // Ignored: polled data is non-critical and the next tick retries
    }
  }

  function start() {
    consumerCount++
    if (consumerCount === 1) {
      refresh()
      intervalId = setInterval(refresh, intervalMs)
    }
  }

  function stop() {
    if (consumerCount > 0) consumerCount--
    if (consumerCount === 0 && intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  return { data, refresh, start, stop }
}
