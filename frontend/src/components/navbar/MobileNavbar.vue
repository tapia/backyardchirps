<template>
  <nav class="mobile-nav d-sm-none">
    <div class="mobile-nav-bar">
      <RouterLink class="navbar-brand" to="/" @click="close">
        <i class="bi bi-feather me-2"></i><span>Backyard Chirps</span>
      </RouterLink>
      <button
        type="button"
        class="mobile-nav-toggler"
        :aria-expanded="isOpen"
        :aria-label="t('nav.toggle')"
        @click="toggle"
      >
        <i class="bi" :class="isOpen ? 'bi-x-lg' : 'bi-list'"></i>
      </button>
    </div>

    <div v-if="isOpen" class="mobile-nav-backdrop" @click="close"></div>

    <div ref="panel" class="mobile-nav-panel" :class="{ open: isOpen }">
      <div class="mobile-weather-card">
        <WeatherWidget />
      </div>

      <div class="mobile-search">
        <SpeciesSearchPicker ref="searchPicker" floating :list-height="260" @select="goToSpecies" />
      </div>

      <div class="list-group mobile-nav-cards">
        <RouterLink
          v-for="page in visiblePages"
          :key="page.routeName"
          class="list-group-item list-group-item-action mobile-nav-card"
          :to="page.to"
          @click="close"
        >
          <span class="mobile-nav-card-icon"><i class="bi" :class="page.icon"></i></span>
          <span class="mobile-nav-card-text">
            <span class="mobile-nav-card-title"
              >{{ t(page.labelKey)
              }}<span v-if="page.routeName === 'pending' && pendingCount" class="pending-badge">{{
                pendingCount
              }}</span></span
            >
            <span class="mobile-nav-card-subtitle">{{ t(page.subtitleKey) }}</span>
          </span>
          <i class="bi bi-chevron-right mobile-nav-card-chevron"></i>
        </RouterLink>
      </div>

      <h3 class="mobile-filters-title">{{ t('nav.quickFilters') }}</h3>

      <div class="mobile-filters-grid">
        <div class="mobile-filter-cell">
          <span class="mobile-filter-label">
            <i class="bi bi-shield-check"></i>{{ t('filter.minConfidence') }}
          </span>
          <div class="btn-group btn-group-sm w-100">
            <button
              v-for="opt in confidenceOptions"
              :key="opt.value"
              type="button"
              class="btn"
              :class="confidenceLevel === opt.value ? 'btn-primary' : 'btn-outline-primary'"
              @click="confidenceLevel = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <div class="mobile-filter-divider"></div>
        <div class="mobile-filter-cell">
          <span class="mobile-filter-label">
            <i class="bi bi-translate"></i>{{ t('nav.language') }}
          </span>
          <div class="btn-group btn-group-sm w-100">
            <button
              v-for="option in LANGUAGE_OPTIONS"
              :key="option.value"
              type="button"
              class="btn"
              :class="locale === option.value ? 'btn-primary' : 'btn-outline-primary'"
              @click="locale = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </div>

      <div class="list-group mobile-nav-cards">
        <RouterLink
          class="list-group-item list-group-item-action mobile-admin-item"
          to="/detections"
          @click="close"
        >
          <i class="bi bi-card-list"></i>{{ t('nav.allDetections') }}
        </RouterLink>
      </div>

      <h3 class="mobile-filters-title">{{ t('nav.admin') }}</h3>

      <div class="list-group mobile-nav-cards mobile-admin-list">
        <RouterLink
          v-if="!currentUser || !currentUser.is_staff"
          class="list-group-item list-group-item-action mobile-admin-item"
          to="/login"
          @click="close"
        >
          <i class="bi bi-shield-lock"></i>{{ t('nav.logIn') }}
        </RouterLink>
        <template v-else>
          <RouterLink
            class="list-group-item list-group-item-action mobile-admin-item"
            to="/settings"
            @click="close"
          >
            <i class="bi bi-gear"></i>{{ t('nav.settings') }}
          </RouterLink>
          <RouterLink
            class="list-group-item list-group-item-action mobile-admin-item"
            to="/detection-settings"
            @click="close"
          >
            <i class="bi bi-sliders"></i>{{ t('detectionSettings.pageTitle') }}
          </RouterLink>
          <RouterLink
            class="list-group-item list-group-item-action mobile-admin-item"
            to="/server-status"
            @click="close"
          >
            <i class="bi bi-hdd-rack"></i>{{ t('nav.serverStatus')
            }}<span v-if="serverStatus?.alert" class="status-alert-dot ms-2"></span>
          </RouterLink>
          <a
            class="list-group-item list-group-item-action mobile-admin-item"
            href="#"
            @click.prevent="onLogout"
          >
            <i class="bi bi-box-arrow-right"></i>{{ t('nav.logout') }}
          </a>
        </template>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDubiousCount } from '../../composables/useDubiousCount.js'
import { useAuth } from '../../composables/useAuth.js'
import { useServerStatus } from '../../composables/useServerStatus.js'
import { useConfidenceFilter } from '../../composables/useConfidenceFilter.js'
import { LANGUAGE_OPTIONS } from '../../locales/languageOptions.js'
import { speciesRoute } from '../../links.js'
import WeatherWidget from '../common/WeatherWidget.vue'
import SpeciesSearchPicker from '../species/SpeciesSearchPicker.vue'
import { visibleNavPages } from './navPages.js'

const emit = defineEmits(['logout'])

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const { pendingCount } = useDubiousCount()
const { currentUser } = useAuth()

// The review queue is admin-only, so it is left out of the navbar rather than shown
// and then refused.
const visiblePages = computed(() => visibleNavPages(currentUser.value?.is_staff))
const { status: serverStatus } = useServerStatus()
const { confidenceLevel, confidenceOptions } = useConfidenceFilter()

const isOpen = ref(false)
const panel = ref(null)
const searchPicker = ref(null)

// Close the overlay whenever the route changes (e.g. browser back button).
watch(
  () => route.fullPath,
  () => close(),
)

function toggle() {
  isOpen.value = !isOpen.value
  // Always reveal the menu scrolled to the top, regardless of where it was
  // left the previous time it was opened.
  if (isOpen.value) {
    nextTick(() => {
      if (panel.value) panel.value.scrollTop = 0
    })
  }
}

function close() {
  isOpen.value = false
  searchPicker.value?.clear()
}

function goToSpecies(species) {
  router.push(speciesRoute(species.slug))
  close()
}

function onLogout() {
  close()
  emit('logout')
}
</script>

<style scoped>
.mobile-nav {
  position: relative;
  background: var(--paper);
  border-bottom: 1px solid var(--limestone);
  margin-bottom: 0.5rem;
}
.mobile-nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.45rem 1rem;
}
.mobile-nav-bar .navbar-brand {
  margin: 0;
}
.mobile-nav-toggler {
  border: none;
  background: none;
  color: var(--graphite);
  font-size: 1.35rem;
  line-height: 1;
  padding: 0.25rem 0.4rem;
}
.mobile-nav-toggler:focus {
  outline: none;
}

.mobile-nav-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1029;
  background: rgba(0, 0, 0, 0.15);
}

/* The panel overlays the page from just below the top bar. */
.mobile-nav-panel {
  display: none;
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1030;
  max-height: calc(100vh - 100%);
  overflow-y: auto;
  padding: 0.75rem 1rem 1.25rem;
  background: var(--paper);
  border-top: 1px solid var(--limestone);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08);
}
.mobile-nav-panel.open {
  display: block;
}

/* ── Weather ─────────────────────────────────────────── */
.mobile-weather-card {
  border: 1px solid var(--limestone);
  border-radius: 12px;
  background: var(--sheet);
  margin-bottom: 0.9rem;
}
.mobile-weather-card :deep(.weather-widget) {
  width: 100%;
  justify-content: space-between;
  padding: 0.6rem 0.9rem;
}

/* ── Navigation list group ───────────────────────────── */
.mobile-nav-cards {
  margin-bottom: 1rem;
  border-radius: 12px;
  --bs-list-group-bg: var(--sheet);
  --bs-list-group-border-color: var(--limestone);
  --bs-list-group-border-radius: 12px;
  --bs-list-group-action-hover-bg: var(--lichen-pale);
  --bs-list-group-action-hover-color: var(--graphite);
  --bs-list-group-action-active-bg: var(--lichen-pale);
  --bs-list-group-action-active-color: var(--graphite);
}
.mobile-nav-card {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 0.85rem 1rem;
}
.mobile-nav-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 50%;
  background: var(--lichen-pale);
  color: var(--lichen);
  font-size: 1.15rem;
}
.mobile-nav-card-text {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  min-width: 0;
  line-height: 1.2;
}
.mobile-nav-card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-sans);
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--graphite);
}
.mobile-nav-card-title .pending-badge {
  min-width: 1.6rem;
  height: 1.6rem;
  border-radius: 0.8rem;
  font-size: 0.8rem;
}
.mobile-nav-card-subtitle {
  font-size: 0.85rem;
  color: var(--slate);
}
.mobile-nav-card-chevron {
  flex-shrink: 0;
  color: var(--dust);
  font-size: 1.1rem;
}

/* ── Search ──────────────────────────────────────────── */
.mobile-search {
  margin-bottom: 1rem;
}
.mobile-search :deep(.search-input) {
  border-radius: 12px;
  padding: 0.7rem 1rem 0.7rem 2.6rem;
  font-size: 1rem;
}
.mobile-search :deep(.search-leading-icon) {
  left: 1rem;
  font-size: 1rem;
}

/* ── Quick filters ───────────────────────────────────── */
.mobile-filters-title {
  font-family: var(--font-sans);
  font-size: 1rem;
  font-weight: 600;
  color: var(--graphite);
  margin: 0 0 0.6rem;
}
.mobile-filters-grid {
  display: flex;
  align-items: stretch;
  gap: 0.75rem;
  padding: 0.9rem;
  margin-bottom: 0.75rem;
  border: 1px solid var(--limestone);
  border-radius: 12px;
  background: var(--sheet);
}
.mobile-filter-cell {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1 1 0;
  min-width: 0;
}
.mobile-filter-divider {
  width: 1px;
  background: var(--limestone);
  flex-shrink: 0;
}
.mobile-filter-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--slate);
}
.mobile-filter-label i {
  color: var(--lichen);
}

/* ── Admin ───────────────────────────────────────────── */
.mobile-admin-list {
  margin-bottom: 0;
}
.mobile-admin-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.75rem 1rem;
  font-size: 0.95rem;
  color: var(--slate);
}
.mobile-admin-item > i {
  color: var(--lichen);
  font-size: 1.05rem;
}
</style>
