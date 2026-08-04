<template>
  <span
    v-if="label"
    class="detection-badge"
    :class="`detection-badge--${variant}`"
    v-bs-tooltip="tooltip"
  >
    <i class="bi" :class="icon" aria-hidden="true"></i>{{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  detectionSettings: {
    type: Object,
    default: () => ({ blacklisted: false, auto_confirm_threshold: null }),
  },
})

const { t } = useI18n()

// Blacklisting takes priority over a custom threshold: a blacklisted species has
// no detections at all regardless of its threshold, so the blacklisted state is
// the one worth surfacing.
const variant = computed(() => {
  if (props.detectionSettings.blacklisted) return 'blacklisted'
  if (props.detectionSettings.auto_confirm_threshold !== null) return 'threshold'
  return null
})

const label = computed(() => {
  if (variant.value === 'blacklisted') return t('detectionSettings.blacklistedBadge')
  if (variant.value === 'threshold') {
    const value = `${Math.round(props.detectionSettings.auto_confirm_threshold * 100)}%`
    return t('detectionSettings.customThresholdBadge', { value })
  }
  return null
})

const icon = computed(() => (variant.value === 'blacklisted' ? 'bi-eye-slash-fill' : 'bi-sliders'))

const tooltip = computed(() =>
  variant.value === 'blacklisted'
    ? t('detectionSettings.blacklistedTooltip')
    : t('detectionSettings.thresholdTooltip'),
)
</script>

<style scoped>
.detection-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
  line-height: 1;
}
.detection-badge .bi {
  font-size: 0.95rem;
}
/* Blacklisted: a prominent amber pill so a suppressed species stands out at a glance. */
.detection-badge--blacklisted {
  background: rgba(var(--dawn-amber-rgb), 0.28);
  border: 1px solid rgba(var(--dawn-amber-rgb), 0.65);
  color: var(--ochre);
}
/* Custom threshold: a quieter lichen pill. */
.detection-badge--threshold {
  background: rgba(var(--lichen-rgb), 0.14);
  border: 1px solid rgba(var(--lichen-rgb), 0.4);
  color: var(--lichen-dark);
}
</style>
