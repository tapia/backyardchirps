import client from './client.js'

export async function fetchServerStatus() {
  const { data } = await client.get('/api/server-status/')
  return data
}
