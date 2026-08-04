<template>
  <div ref="dropdownEl" class="dropdown d-none d-sm-block">
    <button
      class="btn btn-outline-primary btn-sm dropdown-toggle"
      type="button"
      data-bs-toggle="dropdown"
    >
      <span v-if="currentUser?.is_staff && serverStatus?.alert" class="status-alert-badge me-1"
        ><i class="bi bi-exclamation-triangle-fill"></i
      ></span>
      <i class="bi bi-gear"></i>
    </button>
    <ul class="dropdown-menu dropdown-menu-end">
      <li class="dropdown-submenu">
        <span
          class="dropdown-item dropdown-submenu-toggle d-flex align-items-center"
          @click.stop="toggleSubmenu('confidence')"
        >
          <i class="bi bi-chevron-left submenu-caret"></i>
          <span><i class="bi bi-shield-check me-2"></i>{{ t('filter.minConfidence') }}</span>
        </span>
        <ul class="dropdown-menu submenu" :class="{ show: openSubmenu === 'confidence' }">
          <li v-for="opt in confidenceOptions" :key="opt.value">
            <a
              class="dropdown-item"
              :class="{ 'submenu-selected': confidenceLevel === opt.value }"
              href="#"
              @click.prevent="confidenceLevel = opt.value"
            >
              <i
                class="bi bi-check2 submenu-tick me-2"
                :class="{ invisible: confidenceLevel !== opt.value }"
              ></i
              >{{ opt.label }}</a
            >
          </li>
        </ul>
      </li>
      <li class="dropdown-submenu">
        <span
          class="dropdown-item dropdown-submenu-toggle d-flex align-items-center"
          @click.stop="toggleSubmenu('language')"
        >
          <i class="bi bi-chevron-left submenu-caret"></i>
          <span><i class="bi bi-translate me-2"></i>{{ t('nav.language') }}</span>
        </span>
        <ul class="dropdown-menu submenu" :class="{ show: openSubmenu === 'language' }">
          <li v-for="option in LANGUAGE_OPTIONS" :key="option.value">
            <a
              class="dropdown-item"
              :class="{ 'submenu-selected': locale === option.value }"
              href="#"
              @click.prevent="locale = option.value"
            >
              <i
                class="bi bi-check2 submenu-tick me-2"
                :class="{ invisible: locale !== option.value }"
              ></i
              >{{ option.label }}</a
            >
          </li>
        </ul>
      </li>
      <li>
        <RouterLink class="dropdown-item" to="/detections" @click="emit('navigate')">
          <i class="bi bi-card-list me-2"></i>{{ t('nav.allDetections') }}
        </RouterLink>
      </li>
      <li v-if="currentUser?.is_staff" class="dropdown-submenu">
        <span
          class="dropdown-item dropdown-submenu-toggle d-flex align-items-center"
          @click.stop="toggleSubmenu('admin')"
        >
          <i class="bi bi-chevron-left submenu-caret"></i>
          <span
            ><span v-if="serverStatus?.alert" class="status-alert-badge me-2"
              ><i class="bi bi-exclamation-triangle-fill"></i></span
            ><i v-else class="bi bi-shield-lock me-2"></i>{{ currentUser.username }}</span
          >
        </span>
        <ul class="dropdown-menu submenu" :class="{ show: openSubmenu === 'admin' }">
          <li>
            <RouterLink class="dropdown-item" to="/settings" @click="emit('navigate')">
              <i class="bi bi-gear me-2"></i>{{ t('nav.settings') }}
            </RouterLink>
          </li>
          <li>
            <RouterLink class="dropdown-item" to="/detection-settings" @click="emit('navigate')">
              <i class="bi bi-sliders me-2"></i>{{ t('detectionSettings.pageTitle') }}
            </RouterLink>
          </li>
          <li>
            <RouterLink class="dropdown-item" to="/server-status" @click="emit('navigate')">
              <i class="bi bi-hdd-rack me-2"></i>{{ t('nav.serverStatus')
              }}<span v-if="serverStatus?.alert" class="status-alert-dot ms-2"></span>
            </RouterLink>
          </li>
          <li><hr class="dropdown-divider" /></li>
          <li>
            <a class="dropdown-item" href="#" @click.prevent="emit('logout')">
              <i class="bi bi-box-arrow-right me-2"></i>{{ t('nav.logout') }}
            </a>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../../composables/useAuth.js'
import { useServerStatus } from '../../composables/useServerStatus.js'
import { useConfidenceFilter } from '../../composables/useConfidenceFilter.js'
import { LANGUAGE_OPTIONS } from '../../locales/languageOptions.js'

const emit = defineEmits(['navigate', 'logout'])

const { t, locale } = useI18n()
const { currentUser } = useAuth()
const { status: serverStatus } = useServerStatus()
const { confidenceLevel, confidenceOptions } = useConfidenceFilter()

const dropdownEl = ref(null)
const openSubmenu = ref(null)

function toggleSubmenu(name) {
  openSubmenu.value = openSubmenu.value === name ? null : name
}

function resetSubmenu() {
  openSubmenu.value = null
}

onMounted(() => {
  dropdownEl.value?.addEventListener('hidden.bs.dropdown', resetSubmenu)
})

onUnmounted(() => {
  dropdownEl.value?.removeEventListener('hidden.bs.dropdown', resetSubmenu)
})
</script>

<style>
.dropdown-submenu {
  position: relative;
}
.dropdown-submenu-toggle {
  cursor: pointer;
  gap: 1rem;
}
.submenu-caret {
  font-size: 0.7rem;
  color: var(--slate);
}
.submenu-selected {
  background-color: var(--sand-pale);
}
.dropdown-submenu > .dropdown-menu.submenu {
  top: 0;
  right: 100%;
  left: auto;
  margin-top: 0;
}
@media (hover: hover) {
  .dropdown-submenu:hover > .dropdown-menu.submenu {
    display: block;
  }
}
</style>
