import { fetchCurrentWeather } from '../api/index.js'
import { createPolledResource } from './createPolledResource.js'

const polledWeather = createPolledResource(fetchCurrentWeather, 5 * 60 * 1000)

export function useWeather() {
  return { weather: polledWeather.data, start: polledWeather.start, stop: polledWeather.stop }
}
