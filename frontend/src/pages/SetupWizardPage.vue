<template>
  <div class="setup-page">
    <div class="setup-card settings-card">
      <div class="setup-header">
        <h5 class="mb-1"><i class="bi bi-binoculars me-2"></i>{{ t('setup.title') }}</h5>
        <p class="setup-step-count mb-0">
          {{ t('setup.stepCount', { current: stepNumber, total: STEPS.length }) }}
        </p>
      </div>

      <div class="progress setup-progress mb-4">
        <div class="progress-bar" :style="{ width: `${progressPercent}%` }"></div>
      </div>

      <h6 class="setup-step-title">{{ t(`setup.${currentStep}.title`) }}</h6>

      <SetupStepLanguage v-if="currentStep === 'language'" />
      <SetupStepAdmin
        v-else-if="currentStep === 'admin'"
        :token-required="tokenRequired"
        @done="next"
      />
      <SetupStepLocation v-else-if="currentStep === 'location'" :form="location" />
      <SetupStepMicrophone v-else-if="currentStep === 'microphone'" />
      <SetupStepDetection v-else-if="currentStep === 'detection'" :form="analysis" />
      <SetupStepNotifications v-else-if="currentStep === 'notifications'" :form="notifications" />

      <div v-else-if="currentStep === 'done'">
        <p class="step-intro">{{ t('setup.done.intro') }}</p>
        <p v-if="finishError" class="alert alert-danger py-2 small">{{ finishError }}</p>
        <p v-else-if="!recorderStarted && finished" class="alert alert-warning py-2 small">
          {{ t('setup.done.recorderNotStarted') }}
        </p>
      </div>

      <div v-if="currentStep !== 'admin'" class="setup-actions">
        <button
          v-if="canGoBack"
          type="button"
          class="btn btn-outline-light btn-sm"
          :disabled="busy"
          @click="back"
        >
          {{ t('setup.back') }}
        </button>
        <button type="button" class="btn btn-primary btn-sm ms-auto" :disabled="busy" @click="next">
          <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
          {{ currentStep === 'done' ? t('setup.finish') : t('setup.next') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchSettings, completeSetup } from '../api/index.js'
import { useSettingsForm } from '../composables/useSettingsForm.js'
import { useSetup } from '../composables/useSetup.js'
import SetupStepLanguage from '../components/setup/SetupStepLanguage.vue'
import SetupStepAdmin from '../components/setup/SetupStepAdmin.vue'
import SetupStepLocation from '../components/setup/SetupStepLocation.vue'
import SetupStepMicrophone from '../components/setup/SetupStepMicrophone.vue'
import SetupStepDetection from '../components/setup/SetupStepDetection.vue'
import SetupStepNotifications from '../components/setup/SetupStepNotifications.vue'

// The admin step comes second because everything after it needs an account: the
// settings API the later steps write through is admin-only.
const STEPS = ['language', 'admin', 'location', 'microphone', 'detection', 'notifications', 'done']

const router = useRouter()
const { t } = useI18n()
const { status, refresh } = useSetup()

const stepIndex = ref(0)
const busy = ref(false)
const finished = ref(false)
const recorderStarted = ref(false)
const finishError = ref('')

const currentStep = computed(() => STEPS[stepIndex.value])
const stepNumber = computed(() => stepIndex.value + 1)
const progressPercent = computed(() => ((stepIndex.value + 1) / STEPS.length) * 100)
const tokenRequired = computed(() => status.value?.token_required ?? false)
// Never back into the admin step: the account exists by then and creating it again is
// refused, so the form could only fail.
const canGoBack = computed(() => stepIndex.value > STEPS.indexOf('admin') + 1)

// Each of these saves through the ordinary settings API, so the wizard and the settings
// page cannot drift apart on validation or on what a field is called.
const location = useSettingsForm({ location_lat: '', location_lon: '' })
const analysis = useSettingsForm({
  analysis_low_confidence: '',
  analysis_medium_confidence: '',
  analysis_high_confidence: '',
})
const notifications = useSettingsForm({
  telegram_token: '',
  telegram_chat_id: '',
  notifications_language: 'es',
  xeno_canto_api_key: '',
  ipgeolocation_api_key: '',
})

const FORM_BY_STEP = { location, microphone: null, detection: analysis, notifications }

onMounted(async () => {
  // Only reachable once there is an account, which is why this waits for the admin step
  // rather than running on mount for an anonymous visitor.
  if (!status.value?.has_admin) return
  await loadSettings()
})

async function loadSettings() {
  const settings = await fetchSettings()
  for (const form of [location, analysis, notifications]) form.load(settings)
}

async function next() {
  const form = FORM_BY_STEP[currentStep.value]
  busy.value = true
  try {
    if (form) {
      await form.save()
      // save() reports per-field errors on the form itself rather than throwing, so
      // staying on the step is how the user gets to see them.
      if (Object.values(form.errors).some(Boolean)) return
    }
    if (currentStep.value === 'admin') await loadSettings()
    if (currentStep.value === 'done') {
      await finish()
      return
    }
    stepIndex.value += 1
  } finally {
    busy.value = false
  }
}

function back() {
  if (stepIndex.value > 0) stepIndex.value -= 1
}

async function finish() {
  finishError.value = ''
  try {
    recorderStarted.value = await completeSetup()
    finished.value = true
    await refresh()
    router.push('/')
  } catch (error) {
    const code = error.response?.data?.error
    finishError.value = code ? t(`setup.errors.${code}`) : t('setup.errors.unreachable')
  }
}
</script>

<style scoped>
.setup-page {
  display: flex;
  justify-content: center;
  padding: 2rem 1rem 4rem;
}
.setup-card {
  width: 100%;
  max-width: 480px;
}
.setup-header {
  margin-bottom: 1rem;
}
.setup-header h5 {
  color: #fff;
}
.setup-step-count {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
}
.setup-progress {
  height: 4px;
  background-color: rgba(255, 255, 255, 0.1);
}
.setup-progress .progress-bar {
  background-color: var(--admin-accent);
}
.setup-step-title {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 1rem;
}
.setup-actions {
  display: flex;
  margin-top: 1.5rem;
}
</style>

<!-- Unscoped, like the settings card rules these steps borrow: the step components
     render their own markup and would not be reached by a scoped selector. -->
<style>
.setup-card .step-intro {
  color: rgba(255, 255, 255, 0.65);
  font-size: 0.875rem;
  margin-bottom: 1.25rem;
}
</style>
