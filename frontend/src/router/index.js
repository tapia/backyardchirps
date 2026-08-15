import { createRouter, createWebHistory } from 'vue-router'
import DetectionsFeedPage from '../pages/DetectionsFeedPage.vue'
import AllDetectionsPage from '../pages/AllDetectionsPage.vue'
import SpeciesListPage from '../pages/SpeciesListPage.vue'
import SpeciesProfilePage from '../pages/SpeciesProfilePage.vue'
import RecordingDetailPage from '../pages/RecordingDetailPage.vue'
import PendingReviewPage from '../pages/PendingReviewPage.vue'
import LoginPage from '../pages/LoginPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import DetectionSettingsPage from '../pages/DetectionSettingsPage.vue'
import ServerStatusPage from '../pages/ServerStatusPage.vue'
import { useAuth } from '../composables/useAuth.js'
import { useSetup } from '../composables/useSetup.js'

const routes = [
  { path: '/', name: 'recent', component: DetectionsFeedPage },
  { path: '/detections', name: 'all-detections', component: AllDetectionsPage },
  { path: '/species', name: 'species', component: SpeciesListPage },
  { path: '/species/:slug', name: 'species-detail', component: SpeciesProfilePage },
  { path: '/recordings/:id', name: 'recording-detail', component: RecordingDetailPage },
  { path: '/pending-review', name: 'pending', component: PendingReviewPage },
  { path: '/login', name: 'login', component: LoginPage },
  { path: '/settings', name: 'settings', component: SettingsPage, meta: { requiresAdmin: true } },
  {
    path: '/detection-settings',
    name: 'detection-settings',
    component: DetectionSettingsPage,
    meta: { requiresAdmin: true },
  },
  {
    path: '/server-status',
    name: 'server-status',
    component: ServerStatusPage,
    meta: { requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// An unconfigured station has no coordinates and is not even recording yet, so there is
// nothing to look at anywhere else. Everything goes to the wizard until it is finished.
//
// The wizard is served by Django at /setup/ rather than being part of this app, so going
// there is a page load and not a route change. Returning false stops the navigation this
// one replaces.
router.beforeEach(async () => {
  const { status, ready: setupReady } = useSetup()
  await setupReady()

  if (!status.value.is_complete) {
    window.location.href = '/setup/'
    return false
  }
  return true
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAdmin) return true

  const { currentUser, ready } = useAuth()
  await ready()

  if (!currentUser.value?.is_staff) {
    return { name: 'login', query: { next: to.fullPath } }
  }

  return true
})

export default router
