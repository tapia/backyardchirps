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
    </div>

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
import { fetchAvailableUpdate } from '../api/index.js'
import ServerStatusMetricCard from '../components/common/ServerStatusMetricCard.vue'

const { t } = useI18n()
const { status, start, stop } = useServerStatus()

// Fetched once rather than polled with the metrics beside it. The answer comes from a
// stored result that a timer refreshes daily, so polling it every five seconds would ask
// the same question 17,000 times for one change.
const update = ref(null)

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
})
onUnmounted(() => stop())
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

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  max-width: 800px;
}
</style>
