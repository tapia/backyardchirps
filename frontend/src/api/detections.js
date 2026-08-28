import client, { dropEmptyParams } from './client.js'
import { speciesUrl } from './species.js'

export async function fetchDetection(detectionId, { lang } = {}) {
  const { data } = await client.get(`/api/detections/${detectionId}/`, { params: { lang } })
  return data
}

// A paginated feed of every detection, newest first, optionally filtered by
// species (scientific name) and/or a [start, end] date range.
// Returns { total, detections }.
export async function fetchAllDetections({ lang, offset, limit, species, start, end } = {}) {
  const { data } = await client.get('/api/detections/', {
    params: dropEmptyParams({ lang, offset, limit, species, start, end }),
  })
  return data
}

// Detection counts for one species, bucketed by hour of day (0-23).
export async function fetchDetectionsPerHourOfDay(speciesSlug, { start, end } = {}) {
  const { data } = await client.get(speciesUrl(speciesSlug, 'hourly/'), {
    params: dropEmptyParams({ start, end }),
  })
  return data.hourly
}

// Detection counts for one species on a date × hour grid.
// Returns { heatmap, x_labels, granularity }.
export async function fetchDetectionsHeatmap(speciesSlug, { start, end } = {}) {
  const { data } = await client.get(speciesUrl(speciesSlug, 'heatmap/'), {
    params: dropEmptyParams({ start, end }),
  })
  return data
}

// Daily detection counts for one species over the last year.
export async function fetchDetectionsPerDayOverLastYear(speciesSlug) {
  const { data } = await client.get(speciesUrl(speciesSlug, 'yearly/'))
  return data.daily
}

// Detection counts for every species over a 24-hour window, one bucket per hour,
// plus sunrise/sunset times. daysBack shifts the window into the past (0 = ending now).
// Returns { hours, astro }.
export async function fetchDetectionsPerSpeciesPerHour({ lang, daysBack } = {}) {
  const { data } = await client.get('/api/detections/hourly/', {
    params: dropEmptyParams({ lang, offset: daysBack || undefined }),
  })
  return data
}

// Detection counts for the given species bucketed by clock hour (0-23) summed
// across the period, in the requested order. Returns { species, days }.
export async function fetchDetectionsByHourOfDay({ speciesSlugs, lang, start, end } = {}) {
  // Hand-built query string: the endpoint expects the species param repeated
  // (?species=a&species=b), which axios' default array serialization doesn't produce.
  const params = new URLSearchParams()
  for (const speciesSlug of speciesSlugs) params.append('species', speciesSlug)
  for (const [key, value] of Object.entries(dropEmptyParams({ lang, start, end }))) {
    params.append(key, value)
  }
  const { data } = await client.get(`/api/detections/by-hour-of-day/?${params}`)
  return data
}

// Detection-count time series for several species at once.
// Returns { series, granularity }.
export async function fetchDetectionsTimeline({ speciesSlugs, lang, start, end } = {}) {
  // Hand-built query string: the endpoint expects the species param repeated
  // (?species=a&species=b), which axios' default array serialization doesn't produce.
  const params = new URLSearchParams()
  for (const speciesSlug of speciesSlugs) params.append('species', speciesSlug)
  for (const [key, value] of Object.entries(dropEmptyParams({ lang, start, end }))) {
    params.append(key, value)
  }
  const { data } = await client.get(`/api/detections/timeline/?${params}`)
  return data
}

// Returns { detections, count }.
export async function fetchDubiousDetections({ lang } = {}) {
  const { data } = await client.get('/api/detections/dubious/', { params: { lang } })
  return data
}

export async function fetchDubiousCount() {
  const { data } = await client.get('/api/detections/dubious/count/')
  return data.count
}

export async function validateDetection(detectionId, payload) {
  await client.post(`/api/detections/${detectionId}/validate/`, payload)
}

export async function discardDetection(detectionId) {
  await client.delete(`/api/detections/${detectionId}/validate/`)
}

// Applies one action ('confirm' or 'discard') to many detections at once.
// Returns the ids the server actually processed, so a stale selection can be
// reconciled against what still existed.
export async function bulkValidateDetections({ action, ids }) {
  const { data } = await client.post('/api/detections/validate/', { action, ids })
  return data.processed
}
