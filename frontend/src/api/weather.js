import client from './client.js'

export async function fetchCurrentWeather() {
  const { data } = await client.get('/api/weather/current/')
  return data
}
