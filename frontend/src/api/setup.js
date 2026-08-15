import client from './client.js'

// Whether the wizard still has to run. The wizard itself is served by Django at /setup/,
// so this is all the SPA needs to know about setup: whether to go there.
export async function fetchSetupStatus() {
  const { data } = await client.get('/api/setup/status/')
  return data
}

// Also used by the settings page, which lets an admin change the microphone long after
// the wizard is over.
export async function fetchAudioDevices() {
  const { data } = await client.get('/api/setup/audio-devices/')
  return data
}
