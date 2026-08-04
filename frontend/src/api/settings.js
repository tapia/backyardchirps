import client from './client.js'

export async function fetchSettings() {
  const { data } = await client.get('/api/settings/')
  return data
}

export async function saveSettings(settings) {
  await client.put('/api/settings/', settings)
}
