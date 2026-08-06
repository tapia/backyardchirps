import { ref } from 'vue'
import * as api from '../api/index.js'

// Whether the station has been set up. Module-level state, so the router guard and the
// wizard read the same answer rather than each asking the server.
//
// A station is set up exactly once and then never again, so this is fetched once and
// refreshed only when the wizard finishes.
const status = ref(null)
let initPromise = null

async function load() {
  try {
    status.value = await api.fetchSetupStatus()
  } catch {
    // The endpoint is unreachable, which is not something the wizard can fix. Treat the
    // station as set up: sending every visitor to a wizard that cannot load either would
    // lock them out of a site that may be working perfectly well.
    status.value = { is_complete: true, has_admin: true, token_required: false }
  }
  return status.value
}

function ready() {
  if (!initPromise) {
    initPromise = load()
  }
  return initPromise
}

async function refresh() {
  initPromise = load()
  return initPromise
}

export function useSetup() {
  return { status, ready, refresh }
}
