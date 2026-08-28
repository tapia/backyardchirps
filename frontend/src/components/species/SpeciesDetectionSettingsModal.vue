<template>
  <SlidePanel
    v-if="visible"
    :title="t('detectionSettings.modalTitle', { species: commonName })"
    @close="close"
  >
    <div class="ds-field">
      <label class="ds-field-main" :for="blacklistId">
        <span>
          <span class="ds-field-label">{{ t('detectionSettings.blacklistLabel') }}</span>
          <span class="ds-field-hint">{{ t('detectionSettings.blacklistHint') }}</span>
        </span>
        <span class="form-check form-switch ds-switch">
          <input
            :id="blacklistId"
            v-model="blacklisted"
            class="form-check-input"
            type="checkbox"
            role="switch"
            @change="onBlacklistChange"
          />
        </span>
      </label>
    </div>

    <div class="ds-field">
      <label class="ds-field-main" :for="thresholdToggleId">
        <span>
          <span class="ds-field-label">{{ t('detectionSettings.thresholdLabel') }}</span>
          <span class="ds-field-hint">{{ t('detectionSettings.thresholdHint') }}</span>
        </span>
        <span class="form-check form-switch ds-switch">
          <input
            :id="thresholdToggleId"
            v-model="thresholdEnabled"
            class="form-check-input"
            type="checkbox"
            role="switch"
            @change="onThresholdChange"
          />
        </span>
      </label>
      <div v-if="thresholdEnabled" class="ds-threshold-reveal">
        <div class="input-group ds-threshold-group">
          <input
            :id="thresholdId"
            ref="thresholdField"
            v-model="thresholdInput"
            class="form-control ds-threshold-input"
            :class="{ 'is-invalid': showThresholdError }"
            type="number"
            min="0"
            max="100"
            step="1"
            inputmode="numeric"
            :placeholder="t('detectionSettings.thresholdPlaceholder')"
          />
          <span class="input-group-text">%</span>
        </div>
        <div v-if="showThresholdError" class="ds-threshold-error">
          {{ t('detectionSettings.thresholdRange') }}
        </div>
      </div>
    </div>

    <template #footer>
      <button
        type="button"
        class="btn btn-link ds-reset"
        :disabled="saving"
        @click="resetToDefaults"
      >
        {{ t('detectionSettings.reset') }}
      </button>
      <div class="ds-footer-end">
        <button type="button" class="btn btn-light ds-cancel" :disabled="saving" @click="close">
          {{ t('detectionSettings.cancel') }}
        </button>
        <button
          type="button"
          class="btn btn-primary ds-save"
          :disabled="saving || !thresholdValid"
          @click="save"
        >
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          {{ saving ? t('detectionSettings.saving') : t('detectionSettings.save') }}
        </button>
      </div>
    </template>
  </SlidePanel>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { saveSpeciesDetectionSettings, fetchSettings } from '../../api/index.js'
import SlidePanel from '../common/SlidePanel.vue'

const props = defineProps({
  speciesSlug: { type: String, required: true },
  commonName: { type: String, default: '' },
  // Push a history entry while open so the Back button closes the panel. Turn
  // off when a host (e.g. the validation dialog) already manages history.
  backButtonClose: { type: Boolean, default: true },
})

const emit = defineEmits(['updated'])

const { t } = useI18n()

const blacklistId = `ds-blacklist-${props.speciesSlug}`
const thresholdToggleId = `ds-threshold-toggle-${props.speciesSlug}`
const thresholdId = `ds-threshold-${props.speciesSlug}`

const visible = ref(false)
const blacklisted = ref(false)
const thresholdEnabled = ref(false)
const thresholdInput = ref('')
const thresholdField = ref(null)
const saving = ref(false)

// The global auto-confirm bar, used to prefill the input when a species has no
// custom threshold yet, so switching it on starts from the value in effect
// today rather than a blank field. Loaded lazily the first time it's needed.
const defaultThresholdPercent = ref(null)
let defaultLoaded = false

async function loadDefaultThreshold() {
  if (defaultLoaded) return
  try {
    const settings = await fetchSettings()
    defaultThresholdPercent.value = Math.round(
      (settings.analysis_auto_confirm_confidence ?? 0.7) * 100,
    )
    defaultLoaded = true
  } catch {
    // Leave it unset; enabling the switch just starts from a blank field.
  }
}

// The threshold is stored as a 0 to 1 confidence but edited here as a whole
// percentage, matching how it reads on the status badge.
const thresholdPercent = computed(() => {
  const raw = thresholdInput.value
  if (raw === '' || raw === null || raw === undefined) return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : NaN
})

const thresholdValid = computed(() => {
  if (!thresholdEnabled.value) return true
  const percent = thresholdPercent.value
  return percent !== null && !Number.isNaN(percent) && percent >= 0 && percent <= 100
})

const showThresholdError = computed(
  () => thresholdEnabled.value && thresholdInput.value !== '' && !thresholdValid.value,
)

function open(settings) {
  blacklisted.value = Boolean(settings?.blacklisted)
  const threshold = settings?.auto_confirm_threshold
  const hasThreshold = threshold !== null && threshold !== undefined
  // Blacklisting and a custom threshold are mutually exclusive in the UI; if a
  // legacy record has both, show it as blacklisted.
  thresholdEnabled.value = hasThreshold && !blacklisted.value
  thresholdInput.value = hasThreshold ? String(Math.round(threshold * 100)) : ''
  saving.value = false
  visible.value = true
  loadDefaultThreshold()
}

function close() {
  visible.value = false
}

async function save() {
  if (!thresholdValid.value) return
  const threshold = thresholdEnabled.value ? thresholdPercent.value / 100 : null
  saving.value = true
  try {
    const updated = await saveSpeciesDetectionSettings(props.speciesSlug, {
      blacklisted: blacklisted.value,
      autoConfirmThreshold: threshold,
    })
    emit('updated', updated)
    close()
  } finally {
    saving.value = false
  }
}

// Reset the form to the global defaults locally; Save then persists the change,
// which removes the species' override entirely on the backend.
function resetToDefaults() {
  blacklisted.value = false
  thresholdEnabled.value = false
  thresholdInput.value = ''
}

// Blacklisting and a custom threshold are mutually exclusive: enabling one
// switches the other off. Both may be off. These fire only on user interaction,
// so initialising the form in open() never triggers them.
function onBlacklistChange() {
  if (blacklisted.value) thresholdEnabled.value = false
}

async function onThresholdChange() {
  if (!thresholdEnabled.value) return
  blacklisted.value = false
  // Prefill with the global default when the species has no custom value yet.
  if (thresholdInput.value === '') {
    await loadDefaultThreshold()
    if (thresholdInput.value === '' && defaultThresholdPercent.value !== null) {
      thresholdInput.value = String(defaultThresholdPercent.value)
    }
  }
  nextTick(() => thresholdField.value?.focus())
}

// Dismissal: Escape always closes; the Back button closes too unless a host is
// managing history. SlidePanel handles the close button and backdrop.
let historyPushed = false
let closingFromPopState = false

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.stopImmediatePropagation()
    close()
  }
}

function onPopState() {
  closingFromPopState = true
  close()
}

watch(visible, (open) => {
  if (open) {
    document.addEventListener('keydown', onKeydown, true)
    if (props.backButtonClose) {
      window.addEventListener('popstate', onPopState)
      history.pushState({ dsModal: true }, '')
      historyPushed = true
    }
  } else {
    document.removeEventListener('keydown', onKeydown, true)
    window.removeEventListener('popstate', onPopState)
    if (historyPushed && !closingFromPopState) history.back()
    historyPushed = false
    closingFromPopState = false
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown, true)
  window.removeEventListener('popstate', onPopState)
})

defineExpose({ open })
</script>

<style scoped>
.ds-field {
  padding: 14px 0;
  border-top: 1px solid var(--border-soft);
}
.ds-field:first-child {
  border-top: none;
}
.ds-field-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin: 0;
  cursor: pointer;
}
.ds-field-label {
  display: block;
  font-weight: 600;
  color: var(--graphite);
}
.ds-field-hint {
  display: block;
  font-size: 0.82rem;
  color: var(--slate);
  margin-top: 2px;
}
.ds-switch {
  flex-shrink: 0;
  margin: 0;
  padding-left: 2.6em;
}
.ds-threshold-reveal {
  margin-top: 10px;
}
.ds-threshold-group {
  max-width: 160px;
}
.ds-threshold-input {
  background-color: #fff;
}
.ds-threshold-error {
  margin-top: 6px;
  font-size: 0.8rem;
  color: var(--bs-danger);
}
.ds-footer-end {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ds-reset {
  padding: 0;
  color: var(--slate);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.ds-reset:hover {
  color: var(--graphite);
}
.ds-cancel {
  background: var(--paper);
  border-color: var(--border-soft);
  color: var(--graphite);
}
.ds-save,
.ds-cancel {
  font-weight: 600;
  padding: 8px 18px;
  border-radius: 8px;
}
</style>
