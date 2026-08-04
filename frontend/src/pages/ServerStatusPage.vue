<template>
  <div class="container pb-5">
    <div class="d-flex align-items-baseline gap-2 mb-4">
      <h4 class="mb-0">{{ t('page.serverStatus.title') }}</h4>
      <span v-if="status?.version" class="version-badge">v{{ status.version }}</span>
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
import { onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useServerStatus } from '../composables/useServerStatus.js'
import ServerStatusMetricCard from '../components/common/ServerStatusMetricCard.vue'

const { t } = useI18n()
const { status, start, stop } = useServerStatus()

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

onMounted(() => start())
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

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  max-width: 800px;
}
</style>
