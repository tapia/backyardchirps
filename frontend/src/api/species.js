import client, { dropEmptyParams } from './client.js'

export async function fetchSpeciesList({ sort, lang, start, end, minConfidence } = {}) {
  const { data } = await client.get('/api/species/', {
    params: dropEmptyParams({ sort, lang, start, end, min_confidence: minConfidence }),
  })
  return data.species
}

export async function fetchSpeciesDetail(speciesSlug, { lang, start, end, minConfidence } = {}) {
  const { data } = await client.get(speciesUrl(speciesSlug), {
    params: dropEmptyParams({ lang, start, end, min_confidence: minConfidence }),
  })
  return data
}

export async function fetchSpeciesRecordings(
  speciesSlug,
  { sort, direction, start, end, offset, limit } = {},
) {
  const { data } = await client.get(speciesUrl(speciesSlug, 'recordings/'), {
    params: dropEmptyParams({ sort, direction, start, end, offset, limit }),
  })
  return data
}

export async function fetchSpeciesSeasonality(speciesSlug) {
  const { data } = await client.get(speciesUrl(speciesSlug, 'seasonality/'))
  return data.timeline
}

// Detection settings — a species' blacklisted state and custom auto-confirm
// threshold. GET is public (drives badges/banners); PUT/DELETE are staff only.
export async function fetchSpeciesDetectionSettings(speciesSlug) {
  const { data } = await client.get(speciesUrl(speciesSlug, 'detection-settings/'))
  return data
}

export async function saveSpeciesDetectionSettings(
  speciesSlug,
  { blacklisted, autoConfirmThreshold } = {},
) {
  const payload = {}
  if (blacklisted !== undefined) payload.blacklisted = blacklisted
  if (autoConfirmThreshold !== undefined) payload.auto_confirm_threshold = autoConfirmThreshold
  const { data } = await client.put(speciesUrl(speciesSlug, 'detection-settings/'), payload)
  return data
}

export async function clearSpeciesDetectionSettings(speciesSlug) {
  await client.delete(speciesUrl(speciesSlug, 'detection-settings/'))
}

export async function fetchCustomizedSpecies({ lang } = {}) {
  const { data } = await client.get('/api/species/detection-settings/', {
    params: dropEmptyParams({ lang }),
  })
  return data.species
}

// Species are always identified in the API by their slug ("turdus-merula"),
// never the raw scientific name.
export function speciesUrl(speciesSlug, endpoint = '') {
  return `/api/species/${encodeURIComponent(speciesSlug)}/${endpoint}`
}
