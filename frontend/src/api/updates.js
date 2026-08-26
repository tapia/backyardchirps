import client from './client.js'

export async function fetchAvailableUpdate() {
  const { data } = await client.get('/api/updates/available/')
  return data
}

// Looks at the repository there and then instead of waiting for the daily check, and
// answers with the fresh result. It runs on the station and can take a few seconds.
export async function checkForUpdate() {
  const { data } = await client.post('/api/updates/check/')
  return data
}

// Starts the update and returns; it runs on the station, so the browser can be closed.
export async function startUpdate(version) {
  const { data } = await client.post('/api/updates/apply/', { version })
  return data
}

export async function fetchUpdateProgress() {
  const { data } = await client.get('/api/updates/progress/')
  return data
}

// Reinstalls the previous release, and restores the database saved before the update when
// that update crossed a migration. Destructive: the caller confirms first.
export async function rollbackUpdate() {
  const { data } = await client.post('/api/updates/rollback/')
  return data
}
