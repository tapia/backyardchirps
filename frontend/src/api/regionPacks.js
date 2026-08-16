import client from './client.js'

// Region packs: the eBird data a station needs for the part of the world it sits in.
// The wizard installs one during setup; these are for changing it afterwards.

// Which pack covers a point, or the nearest when none does. The coordinates are passed
// rather than read from the settings, so the card can answer for a location that has been
// typed in but not saved yet.
export async function fetchRegionPack(latitude, longitude) {
  const { data } = await client.get('/api/packs/region-pack/', {
    params: { lat: latitude, lon: longitude },
  })
  return data
}

export async function fetchInstalledRegionPack() {
  const { data } = await client.get('/api/packs/installed/')
  return data
}

// Starts the download and returns; it runs on the station, so the browser can be closed.
export async function startRegionPackInstall(id) {
  const { data } = await client.post('/api/packs/install/', { id })
  return data
}

export async function fetchRegionPackInstallProgress() {
  const { data } = await client.get('/api/packs/install/progress/')
  return data
}
