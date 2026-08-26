<template>
  <div class="container pb-5">
    <div class="d-flex align-items-baseline gap-2 mb-4">
      <h4 class="mb-0">{{ t('page.serverStatus.title') }}</h4>
      <span v-if="status?.version" class="version-badge">v{{ status.version }}</span>
      <a
        v-if="update?.update_available"
        class="update-badge"
        :href="update.changelog_url"
        target="_blank"
        rel="noopener"
        v-bs-tooltip="updateTooltip"
      >
        <i class="bi bi-arrow-up-circle" aria-hidden="true"></i>
        {{ t('page.serverStatus.updateAvailable', { version: update.version }) }}
      </a>
      <span v-else-if="update?.error" class="update-note">
        {{ t('page.serverStatus.updateCheckFailed') }}
      </span>
      <span v-else-if="update && !update.checked_at" class="update-note">
        {{ t('page.serverStatus.updateNeverChecked') }}
      </span>
      <button
        v-if="update?.update_available && !running"
        type="button"
        class="btn btn-sm btn-outline-primary update-install"
        :disabled="starting"
        @click="install"
      >
        {{ t('page.serverStatus.updateInstall') }}
      </button>
      <button
        v-if="canRollBack"
        type="button"
        class="btn btn-sm btn-outline-secondary update-install"
        :disabled="starting"
        @click="rollBack"
      >
        {{ t('page.serverStatus.updateRollback') }}
      </button>
      <button
        v-if="!running"
        type="button"
        class="btn btn-sm btn-link update-check"
        :disabled="checking || starting"
        v-bs-tooltip="t('page.serverStatus.updateCheckNow')"
        :aria-label="t('page.serverStatus.updateCheckNow')"
        @click="checkNow"
      >
        <span v-if="checking" class="spinner-border spinner-border-sm" aria-hidden="true"></span>
        <i v-else class="bi bi-arrow-clockwise" aria-hidden="true"></i>
      </button>
    </div>

    <div v-if="running" class="update-progress mb-4" role="status">
      <span class="spinner-border spinner-border-sm" aria-hidden="true"></span>
      <span>
        {{
          progress.step === 'rolling-back' || progress.step === 'restoring'
            ? t('page.serverStatus.updateRollingBack')
            : t('page.serverStatus.updateInstalling', { version: progress.version })
        }}
        <span v-if="stepLabel" class="update-note">· {{ stepLabel }}</span>
      </span>
    </div>

    <div
      v-else-if="watched && progress?.state === 'succeeded'"
      class="alert alert-success py-2 mb-4"
    >
      {{ t('page.serverStatus.updateSucceeded', { version: progress.version }) }}
    </div>

    <div v-else-if="watched && progress?.state === 'failed'" class="alert alert-danger py-2 mb-4">
      {{ t('page.serverStatus.updateFailed', { message: progress.message }) }}
    </div>

    <div v-if="refusal" class="alert alert-warning py-2 mb-4">{{ refusal }}</div>

    <div v-if="!status" class="text-muted small">{{ t('common.loading') }}</div>

    <div v-else-if="status" class="status-grid">
      <ServerStatusMetricCard
        icon="bi-thermometer-half"
        :label="t('page.serverStatus.cpuTemperature')"
        :value="status.cpu_temperature !== null ? status.cpu_temperature + ' °C' : null"
        :unavailable-text="t('page.serverStatus.notAvailable')"
        :is-alert="status.cpu_temperature_alert"
        :bar="
          status.cpu_temperature !== null
            ? { value: status.cpu_temperature, threshold: status.thresholds.cpu_temperature }
            : null
        "
      />

      <ServerStatusMetricCard
        icon="bi-cpu"
        :label="t('page.serverStatus.cpuLoad')"
        :value="status.cpu_load + ' %'"
        :is-alert="status.cpu_load_alert"
        :bar="{ value: status.cpu_load, threshold: status.thresholds.cpu_load }"
      />

      <ServerStatusMetricCard
        icon="bi-memory"
        :label="t('page.serverStatus.memoryUsed')"
        :value="formatMemory(status.memory_used_mb) + ' / ' + formatMemory(status.memory_total_mb)"
        :is-alert="status.memory_alert"
        :bar="{ value: status.memory_percent, threshold: status.thresholds.memory_percent }"
        :sub="status.memory_percent + ' %'"
      />

      <ServerStatusMetricCard
        icon="bi-hdd"
        :label="t('page.serverStatus.diskUsed')"
        :value="status.disk_used_gb + ' GB / ' + status.disk_total_gb + ' GB'"
        :is-alert="status.disk_alert"
        :bar="{ value: status.disk_percent, threshold: status.thresholds.disk_percent }"
        :sub="status.disk_percent + ' %'"
      />

      <ServerStatusMetricCard
        icon="bi-hourglass-split"
        :label="t('page.serverStatus.soundProcessingQueue')"
        :value="
          status.sound_processing_queue.available
            ? status.sound_processing_queue.load_percent + ' %'
            : null
        "
        :unavailable-text="t('page.serverStatus.recorderOffline')"
        :is-alert="status.sound_processing_queue.alert"
        :bar="
          status.sound_processing_queue.available
            ? {
                value: status.sound_processing_queue.load_percent,
                threshold: status.thresholds.sound_processing_queue_load,
              }
            : null
        "
        :sub="
          status.sound_processing_queue.available
            ? queueDetail(status.sound_processing_queue)
            : null
        "
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useServerStatus } from '../composables/useServerStatus.js'
import {
  checkForUpdate,
  fetchAvailableUpdate,
  fetchUpdateProgress,
  rollbackUpdate,
  startUpdate,
} from '../api/index.js'
import ServerStatusMetricCard from '../components/common/ServerStatusMetricCard.vue'

const { t, te } = useI18n()
const { status, start, stop } = useServerStatus()

// Fetched once rather than polled with the metrics beside it. The answer comes from a
// stored result that a timer refreshes daily, so polling it every five seconds would ask
// the same question 17,000 times for one change.
const update = ref(null)

const progress = ref(null)
const starting = ref(false)
const checking = ref(false)
const refusal = ref('')
let polling = null

// Whether this page has actually watched an update run, rather than found one that finished
// at some point in the past.
const watched = ref(false)

// When the status file was last written before this page asked for anything, and how many
// polls have come back no newer than that.
let stampBeforeStarting = ''
let pollsWithNothingNewer = 0

// Roughly a minute at the polling interval below. If the updater never writes anything, it
// never started, and a spinner that turns for ever is worse than reporting what the station
// actually says.
const POLLS_TO_WAIT_FOR_THE_UPDATER = 20

const running = computed(() => progress.value?.state === 'running')

const stepLabel = computed(() => {
  const step = progress.value?.step
  if (!step) return ''
  const key = `page.serverStatus.updateStep.${step}`
  return te(key) ? t(key) : step
})

// The daily check is what normally fills this in. This is for the two moments waiting for
// it is wrong: a station installed today, which has never checked, and one whose owner has
// just read that a release is out.
async function checkNow() {
  checking.value = true
  refusal.value = ''
  try {
    update.value = await checkForUpdate()
  } catch (error) {
    const code = error?.response?.data?.error
    const key = `page.serverStatus.updateRefused.${code}`
    refusal.value = code && te(key) ? t(key) : t('page.serverStatus.updateCheckFailed')
  } finally {
    checking.value = false
  }
}

async function install() {
  starting.value = true
  refusal.value = ''
  try {
    await startUpdate(update.value.version)
    // Said here rather than taken from the answer: the station replies before the updater
    // has written anything, so the answer still describes the run before this one.
    startWatching('checking', update.value.version)
    startPolling()
  } catch (error) {
    const code = error?.response?.data?.error
    const key = `page.serverStatus.updateRefused.${code}`
    refusal.value =
      code && te(key) ? t(key) : t('page.serverStatus.updateFailed', { message: code || '' })
  } finally {
    starting.value = false
  }
}

// Offered once an update has finished, and it stays offered after a reload
const canRollBack = computed(() => progress.value?.state === 'succeeded' && !running.value)

async function rollBack() {
  if (!window.confirm(t('page.serverStatus.updateRollbackConfirm'))) return
  starting.value = true
  refusal.value = ''
  try {
    await rollbackUpdate()
    startWatching('rolling-back', '')
    startPolling()
  } catch (error) {
    const code = error?.response?.data?.error
    const key = `page.serverStatus.updateRefused.${code}`
    refusal.value =
      code && te(key) ? t(key) : t('page.serverStatus.updateFailed', { message: code || '' })
  } finally {
    starting.value = false
  }
}

function startPolling() {
  stopPolling()
  polling = window.setInterval(poll, 3000)
}

function stopPolling() {
  if (polling !== null) {
    window.clearInterval(polling)
    polling = null
  }
}

// Remember what was on disk before this run, then say what the page knows: the station has
// been asked, and the updater writes its first line a moment later.
function startWatching(step, version) {
  stampBeforeStarting = progress.value?.updated_at ?? ''
  pollsWithNothingNewer = 0
  watched.value = true
  progress.value = { state: 'running', step, message: '', version }
}

// Whether a poll is still describing the run before this one rather than the one just asked
// for. A station whose updater does not stamp the file at all reports nothing here, and then
// this cannot tell and says no, which is what the page did before the stamp existed.
function stillTheRunBefore(polled) {
  if (!polled?.updated_at) return false
  return polled.updated_at <= stampBeforeStarting
}

async function poll() {
  let polled
  try {
    polled = await fetchUpdateProgress()
  } catch {
    // One failed poll says nothing. The web service restarts partway through an update,
    // so a refused request is the expected middle of a run rather than a failure.
    return
  }
  if (stillTheRunBefore(polled) && pollsWithNothingNewer++ < POLLS_TO_WAIT_FOR_THE_UPDATER) return

  progress.value = polled
  if (polled?.state && polled.state !== 'running') stopPolling()
}

const updateTooltip = computed(() => {
  if (!update.value?.released) {
    return t('page.serverStatus.updateChangelog')
  }
  return (
    t('page.serverStatus.updateReleased', { released: update.value.released }) +
    ' · ' +
    t('page.serverStatus.updateChangelog')
  )
})

function formatMemory(megabytes) {
  if (megabytes >= 1024) {
    return (megabytes / 1024).toFixed(1) + ' GB'
  }
  return megabytes + ' MB'
}

function queueDetail(queue) {
  return t('page.serverStatus.soundProcessingQueueDetail', {
    depth: queue.depth,
    peak: queue.depth_peak,
    analysisMs: queue.analysis_ms,
    budgetMs: queue.budget_ms,
  })
}

onMounted(async () => {
  start()
  try {
    update.value = await fetchAvailableUpdate()
  } catch {
    // A station that cannot answer this still shows every metric below it.
    update.value = null
  }
  try {
    progress.value = await fetchUpdateProgress()
    // Picks up an update started before this page was opened, or in another tab. That one
    // does count as watched: whoever is looking at the page sees it finish.
    if (progress.value?.state === 'running') {
      watched.value = true
      startPolling()
    }
  } catch {
    progress.value = null
  }
})
onUnmounted(() => {
  stop()
  stopPolling()
})
</script>

<style scoped>
.version-badge {
  padding: 0.1rem 0.4rem;
  border: 1px solid var(--border-soft);
  border-radius: 4px;
  color: var(--slate);
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
}

.update-check {
  padding: 0 0.25rem;
  color: var(--slate);
  line-height: 1;
}

.update-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.1rem 0.45rem;
  border: 1px solid var(--lichen);
  border-radius: 4px;
  background: var(--lichen-pale);
  color: var(--lichen-dark);
  font-size: 0.7rem;
  text-decoration: none;
}

.update-badge:hover {
  background: var(--lichen);
  color: var(--sheet);
}

.update-note {
  color: var(--slate);
  font-size: 0.7rem;
}

.update-install {
  --bs-btn-padding-y: 0.05rem;
  --bs-btn-padding-x: 0.4rem;
  --bs-btn-font-size: 0.7rem;
}

.update-progress {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--slate);
  font-size: 0.85rem;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  max-width: 800px;
}
</style>
