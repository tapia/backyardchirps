<template>
  <div ref="root" class="dropdown species-actions">
    <button
      type="button"
      class="actions-btn"
      :class="{ 'actions-btn--open': menuOpen }"
      :aria-expanded="menuOpen"
      :aria-label="t('common.actions')"
      v-bs-tooltip="t('common.actions')"
      @click.stop="toggleMenu"
    >
      <i class="bi bi-three-dots"></i>
    </button>
    <ul class="dropdown-menu dropdown-menu-end actions-menu" :class="{ show: menuOpen }">
      <li v-if="isStaff && allowDetectionRules">
        <button type="button" class="dropdown-item" @click="onDetectionRules">
          <i class="bi bi-sliders me-2"></i>{{ t('detectionSettings.menuDetectionRules') }}
        </button>
      </li>
      <li>
        <button type="button" class="dropdown-item" @click="onShare">
          <i class="bi bi-share me-2"></i
          >{{ shareCopied ? t('common.copied') : t('detectionSettings.menuShareSpecies') }}
        </button>
      </li>
    </ul>

    <SpeciesDetectionSettingsModal
      ref="settingsModal"
      :species-slug="speciesSlug"
      :common-name="commonName"
      @updated="emit('settings-updated')"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../../composables/useAuth.js'
import { useShare } from '../../composables/useShare.js'
import SpeciesDetectionSettingsModal from './SpeciesDetectionSettingsModal.vue'

const props = defineProps({
  speciesSlug: { type: String, required: true },
  commonName: { type: String, default: '' },
  // Detection rules only exist for species detected here; hosts turn this off
  // for never-detected species (the backend 404s their detection settings).
  allowDetectionRules: { type: Boolean, default: true },
  detectionSettings: {
    type: Object,
    default: () => ({ blacklisted: false, auto_confirm_threshold: null }),
  },
})

const emit = defineEmits(['settings-updated'])

const { t } = useI18n()
const { currentUser } = useAuth()
const { shareCopied, share } = useShare()

const isStaff = computed(() => Boolean(currentUser.value?.is_staff))
const root = ref(null)
const settingsModal = ref(null)
const menuOpen = ref(false)

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

function openSettings() {
  settingsModal.value?.open(props.detectionSettings)
}

function onDetectionRules() {
  closeMenu()
  openSettings()
}

// Keep the menu open after copying so the "Copied!" acknowledgement is visible;
// an outside click or Escape dismisses it.
function onShare() {
  share(window.location.href)
}

function onDocumentPointer(event) {
  if (!root.value?.contains(event.target)) closeMenu()
}

function onKeydown(event) {
  if (event.key === 'Escape') closeMenu()
}

// Only listen while open, so the menu closes on any outside click or Escape.
watch(menuOpen, (open) => {
  if (open) {
    document.addEventListener('mousedown', onDocumentPointer)
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('mousedown', onDocumentPointer)
    document.removeEventListener('keydown', onKeydown)
  }
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onDocumentPointer)
  document.removeEventListener('keydown', onKeydown)
})

// Exposed so callers (e.g. an "Edit" affordance next to the status badge) can
// open the detection-settings modal without hosting it themselves.
defineExpose({ openSettings })
</script>

<style scoped>
.species-actions {
  position: relative;
}
.actions-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-soft);
  background: #fff;
  color: var(--slate);
  font-size: 1rem;
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s,
    border-color 0.12s;
}
.actions-btn:hover,
.actions-btn--open {
  color: var(--graphite);
  border-color: var(--dust);
}
.actions-menu {
  --bs-dropdown-bg: #fff;
  --bs-dropdown-min-width: 12rem;
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  left: auto;
}
.dropdown-item {
  display: flex;
  align-items: center;
  font-size: 0.9rem;
}
.dropdown-item .bi {
  color: var(--slate);
}
</style>
