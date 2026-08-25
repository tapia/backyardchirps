<template>
  <DesktopNavbar @logout="onLogout" />
  <MobileNavbar @logout="onLogout" />
</template>

<script setup>
import { watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth.js'
import { useDubiousCount } from '../../composables/useDubiousCount.js'
import { useServerStatus } from '../../composables/useServerStatus.js'
import DesktopNavbar from './DesktopNavbar.vue'
import MobileNavbar from './MobileNavbar.vue'

const router = useRouter()
const { currentUser, logout } = useAuth()

// Both of these read an admin-only endpoint: the server status behind the alert badge and
// the status page, and the count behind the review queue's badge. For anyone else every
// tick would come back 403, so they are polled only while a staff user is logged in.
const staffResources = [useServerStatus(), useDubiousCount()]
let staffPolling = false

function setStaffPolling(active) {
  if (active === staffPolling) return
  staffPolling = active
  for (const resource of staffResources) {
    if (active) resource.start()
    else resource.stop()
  }
}

watch(
  () => currentUser.value?.is_staff,
  (isStaff) => setStaffPolling(Boolean(isStaff)),
  {
    immediate: true,
  },
)

onUnmounted(() => setStaffPolling(false))

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
