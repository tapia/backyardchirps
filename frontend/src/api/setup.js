import client from './client.js'
import { setCsrfToken } from './client.js'

export async function fetchSetupStatus() {
  const { data } = await client.get('/api/setup/status/')
  return data
}

// Trades the one-time token the installer printed for a session allowed to run the
// wizard. The CSRF token that comes back belongs to that session, so it replaces the
// one the client was using.
export async function claimSetup(token) {
  const { data } = await client.post('/api/setup/claim/', { token })
  setCsrfToken(data.csrf_token)
  return data
}

// Creates the first admin and logs in as them, which is what lets the rest of the
// wizard use the ordinary settings API.
export async function createSetupAdmin(username, password) {
  const { data } = await client.post('/api/setup/admin/', { username, password })
  setCsrfToken(data.csrf_token)
  return data
}

export async function fetchAudioDevices() {
  const { data } = await client.get('/api/setup/audio-devices/')
  return data
}

export async function saveAudioDevice(device) {
  const { data } = await client.post('/api/setup/audio-device/', { device })
  return data.recorder_restarted
}

export async function fetchAudioLevel(device) {
  const { data } = await client.get('/api/setup/audio-level/', {
    params: device === null || device === '' ? {} : { device },
  })
  return data
}

export async function completeSetup() {
  const { data } = await client.post('/api/setup/complete/')
  return data.recorder_started
}
