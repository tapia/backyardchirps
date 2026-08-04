import client, { setCsrfToken } from './client.js'

export async function fetchCurrentUser() {
  const { data } = await client.get('/api/auth/me/')
  setCsrfToken(data.csrf_token)
  return data
}

export async function login(username, password) {
  const { data } = await client.post('/api/auth/login/', { username, password })
  setCsrfToken(data.csrf_token)
  return data
}

export async function logout() {
  await client.post('/api/auth/logout/')
}
