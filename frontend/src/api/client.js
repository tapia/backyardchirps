import axios from 'axios'

// Shared axios instance for all backend calls. Django's session cookie
// authenticates requests; mutating requests additionally need the CSRF
// token, which auth.js installs here after login / session restore.
const client = axios.create()

export function setCsrfToken(token) {
  client.defaults.headers.common['X-CSRFToken'] = token
}

export function dropEmptyParams(params) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null),
  )
}

export default client
