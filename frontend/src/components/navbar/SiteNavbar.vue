<template>
  <DesktopNavbar @logout="onLogout" />
  <MobileNavbar @logout="onLogout" />
</template>

<script setup>
import { watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth.js'
import { useServerStatus } from '../../composables/useServerStatus.js'
import DesktopNavbar from './DesktopNavbar.vue'
import MobileNavbar from './MobileNavbar.vue'

const router = useRouter()
const { currentUser, logout } = useAuth()
const { start: startServerStatus, stop: stopServerStatus } = useServerStatus()

// Server status is only shown to staff (alert badges, server status page),
// so only poll it while a staff user is logged in.
let serverStatusPolling = false
watch(
  () => currentUser.value?.is_staff,
  (isStaff) => {
    if (isStaff && !serverStatusPolling) {
      serverStatusPolling = true
      startServerStatus()
    } else if (!isStaff && serverStatusPolling) {
      serverStatusPolling = false
      stopServerStatus()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  if (serverStatusPolling) stopServerStatus()
})

async function onLogout() {
  await logout()
  router.push('/')
}
</script>

<style>
/* Badges shared by the desktop dropdown and the mobile navbar. */
.pending-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--lichen);
  color: var(--sheet);
  font-size: 0.58rem;
  font-weight: 600;
  line-height: 1;
}
.status-alert-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 8px;
  background: var(--danger-muted);
  color: var(--sheet);
  font-size: 0.55rem;
  line-height: 1;
  vertical-align: middle;
  margin-bottom: 2px;
}
.status-alert-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--danger-muted);
  vertical-align: middle;
  margin-bottom: 2px;
}
</style>
