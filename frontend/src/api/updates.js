import client from './client.js'

export async function fetchAvailableUpdate() {
  const { data } = await client.get('/api/updates/available/')
  return data
}
