import client from './client.js'

export async function fetchAvailableUpdate() {
  const { data } = await client.get('/api/updates/available/')
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
