import { fetchServerStatus } from '../api/index.js'
import { createPolledResource } from './createPolledResource.js'

const polledStatus = createPolledResource(fetchServerStatus, 5000)

export function useServerStatus() {
  return { status: polledStatus.data, start: polledStatus.start, stop: polledStatus.stop }
}
