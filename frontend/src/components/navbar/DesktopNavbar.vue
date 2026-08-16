<template>
  <nav class="navbar site-nav mb-2 d-none d-sm-flex">
    <div class="container">
      <RouterLink class="navbar-brand" to="/">
        <i class="bi bi-feather me-2"></i><span>Backyard Chirps</span>
      </RouterLink>
      <div class="d-flex align-items-center gap-3 flex-grow-1 justify-content-end">
        <ul
          class="navbar-nav flex-row gap-2 nav-collapsible"
          :class="{ collapsed: searchExpanded }"
        >
          <li v-for="page in NAV_PAGES" :key="page.routeName" class="nav-item">
            <RouterLink
              class="nav-link px-2 d-flex align-items-center gap-1"
              :class="{ active: route.name === page.routeName }"
              :to="page.to"
            >
              <i class="bi me-1" :class="page.icon"></i><span>{{ t(page.labelKey) }}</span
              ><span v-if="page.routeName === 'pending' && pendingCount" class="pending-badge">{{
                pendingCount
              }}</span>
            </RouterLink>
          </li>
        </ul>
        <div class="nav-collapsible" :class="{ collapsed: searchExpanded }">
          <WeatherWidget compact />
        </div>
        <div class="d-flex align-items-center gap-2">
          <RouterLink
            v-if="currentUser && !currentUser.is_staff"
            class="btn btn-outline-secondary btn-sm nav-collapsible"
            :class="{ collapsed: searchExpanded }"
            to="/login"
          >
            <i class="bi bi-shield-lock me-1"></i><span>{{ t('nav.logIn') }}</span>
          </RouterLink>
          <NavbarSearch v-model:expanded="searchExpanded" />
          <NavbarSettingsDropdown @logout="emit('logout')" />
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDubiousCount } from '../../composables/useDubiousCount.js'
import { useAuth } from '../../composables/useAuth.js'
import WeatherWidget from '../common/WeatherWidget.vue'
import NavbarSettingsDropdown from './NavbarSettingsDropdown.vue'
import NavbarSearch from './NavbarSearch.vue'
import { NAV_PAGES } from './navPages.js'

const emit = defineEmits(['logout'])

const route = useRoute()
const { t } = useI18n()
const { pendingCount } = useDubiousCount()
const { currentUser } = useAuth()

const searchExpanded = ref(false)
</script>

<style>
.site-nav {
  position: relative;
  /* Establish a stacking context above page content so the floating search
     dropdown (and the rest of the navbar) always overlays it. Matches the
     mobile navbar's stacking level. */
  z-index: 1030;
  background: var(--paper);
  border-bottom: 1px solid var(--limestone);
  padding-top: 0.3rem;
  padding-bottom: 0.3rem;
}

.site-nav .navbar-nav .nav-link {
  font-family: var(--font-sans);
  font-size: 0.85rem;
  color: var(--slate);
  border-radius: 0;
  padding: 0.4rem 0.75rem;
  border-bottom: 2px solid transparent;
  transition:
    color 0.12s,
    border-color 0.12s;
}
.site-nav .navbar-nav .nav-link:hover {
  color: var(--graphite);
  background: none;
  border-bottom-color: var(--limestone);
}
.site-nav .navbar-nav .nav-link.active {
  color: var(--graphite);
  font-weight: 600;
  background: none;
  border-bottom-color: var(--lichen);
}

/* Items to the left of the search (nav links, weather, login) fade out under
   its expanding overlay. Only opacity changes, so their width is kept and
   nothing reflows. */
.site-nav .nav-collapsible {
  transition: opacity 0.2s ease;
}
.site-nav .nav-collapsible.collapsed {
  opacity: 0;
  pointer-events: none;
}
</style>
