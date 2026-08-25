import { fetchDubiousCount } from '../api/index.js'
import { createPolledResource } from './createPolledResource.js'

// How many detections are waiting for review, for the navbar badge. The endpoint behind it
// is admin-only, so the navbar starts the polling only while a staff user is logged in.
// Left running for everyone else it would be a 403 every ten seconds.
const polledCount = createPolledResource(fetchDubiousCount, 10_000)

export function useDubiousCount() {
  return {
    pendingCount: polledCount.data,
    refresh: polledCount.refresh,
    start: polledCount.start,
    stop: polledCount.stop,
  }
}
