<template>
  <div>
    <p class="step-intro">{{ t('setup.microphone.intro') }}</p>

    <div v-if="loading" class="text-muted small">{{ t('common.loading') }}</div>

    <template v-else>
      <p v-if="!devices.length" class="alert alert-warning py-2 small">
        {{ t('setup.microphone.none') }}
      </p>

      <div v-else class="d-grid gap-2 mb-3">
        <button
          v-for="device in devices"
          :key="device.index"
          type="button"
          class="btn btn-outline-light text-start device-option"
          :class="{ selected: selected === device.index }"
          @click="choose(device.index)"
        >
          <i class="bi bi-check-lg me-2 check"></i>
          {{ device.name }}
          <span v-if="device.is_default" class="badge ms-2">{{
            t('setup.microphone.systemDefault')
          }}</span>
        </button>
      </div>

      <div class="meter-block">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span class="small">{{ t('setup.microphone.level') }}</span>
          <button type="button" class="btn btn-sm btn-outline-light" @click="toggleMeter">
            {{ metering ? t('setup.microphone.stop') : t('setup.microphone.test') }}
          </button>
        </div>

        <div class="meter">
          <div class="meter-fill" :style="{ width: `${Math.round(peak * 100)}%` }"></div>
        </div>

        <p v-if="meterError" class="text-warning small mt-2 mb-0">{{ meterError }}</p>
        <p v-else-if="metering" class="field-hint">{{ t('setup.microphone.speakUp') }}</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchAudioDevices, fetchAudioLevel, saveAudioDevice } from '../../api/index.js'

const { t } = useI18n()

// The endpoint listens for about a second, so asking much faster than this would only
// queue requests behind each other.
const POLL_INTERVAL_MS = 1300

const devices = ref([])
const selected = ref(null)
const loading = ref(true)
const metering = ref(false)
const peak = ref(0)
const meterError = ref('')
let timer = null

onMounted(async () => {
  const data = await fetchAudioDevices()
  devices.value = data.devices
  selected.value = data.selected
  // With nothing chosen yet, start on whatever the system calls its default, which is
  // right on the many stations that have exactly one microphone.
  if (selected.value === null) {
    const fallback = data.devices.find((device) => device.is_default) ?? data.devices[0]
    if (fallback) await choose(fallback.index)
  }
  loading.value = false
})

onUnmounted(stopMeter)

async function choose(index) {
  selected.value = index
  await saveAudioDevice(index)
}

function toggleMeter() {
  if (metering.value) stopMeter()
  else startMeter()
}

function startMeter() {
  meterError.value = ''
  metering.value = true
  readLevel()
}

function stopMeter() {
  metering.value = false
  peak.value = 0
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

async function readLevel() {
  if (!metering.value) return
  try {
    const level = await fetchAudioLevel(selected.value)
    peak.value = level.peak
    meterError.value = ''
  } catch (error) {
    const code = error.response?.data?.error
    meterError.value = code ? t(`setup.errors.${code}`) : t('setup.errors.unreachable')
    // A busy or missing device will not free itself while we hammer it, and a meter
    // that keeps retrying hides the message explaining why it is stuck.
    stopMeter()
    return
  }
  timer = setTimeout(readLevel, POLL_INTERVAL_MS)
}
</script>

<style scoped>
.device-option .check {
  visibility: hidden;
}
.device-option.selected {
  border-color: var(--admin-accent);
  background-color: rgba(var(--admin-accent-rgb), 0.15);
}
.device-option.selected .check {
  visibility: visible;
}
.device-option .badge {
  background-color: rgba(255, 255, 255, 0.15);
  font-weight: 400;
}
.meter-block {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 0.75rem;
}
.meter {
  height: 10px;
  border-radius: 5px;
  background-color: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}
.meter-fill {
  height: 100%;
  background-color: var(--admin-accent);
  transition: width 200ms linear;
}
</style>
