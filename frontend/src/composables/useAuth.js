import { ref } from 'vue'
import * as api from '../api/index.js'

const currentUser = ref(null)
let initPromise = null

async function restoreSession() {
  currentUser.value = await api.fetchCurrentUser()
  return currentUser.value
}

async function login(username, password) {
  currentUser.value = await api.login(username, password)
  return currentUser.value
}

async function logout() {
  await api.logout()
  currentUser.value = { is_authenticated: false }
}

function ready() {
  if (!initPromise) {
    initPromise = restoreSession()
  }
  return initPromise
}

ready()

export function useAuth() {
  return { currentUser, login, logout, ready }
}
