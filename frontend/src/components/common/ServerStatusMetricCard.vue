<template>
  <div class="status-card" :class="{ 'is-alert': isAlert }">
    <i v-if="isAlert" class="bi bi-exclamation-triangle-fill alert-icon"></i>
    <div class="status-icon"><i :class="'bi ' + icon"></i></div>
    <div class="status-label">{{ label }}</div>
    <div class="status-value">
      <template v-if="value !== null">{{ value }}</template>
      <span v-else class="status-unavailable">{{ unavailableText }}</span>
    </div>
    <template v-if="bar !== null">
      <div class="progress mt-2" :style="trackStyle">
        <div class="progress-bar" :class="barColorClass" :style="{ width: barWidth + '%' }"></div>
        <div class="threshold-marker" :style="{ left: barWidth + '%' }"></div>
      </div>
    </template>
    <div v-if="sub" class="status-sub">{{ sub }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  icon: { type: String, required: true },
  label: { type: String, required: true },
  value: { type: String, default: null },
  unavailableText: { type: String, default: '—' },
  isAlert: { type: Boolean, default: false },
  bar: { type: Object, default: null }, // { value: Number, threshold: Number }
  sub: { type: String, default: null },
})

const barColorClass = computed(() =>
  props.bar && props.bar.value >= props.bar.threshold ? 'bg-danger' : 'bg-success',
)

// The fill and value marker stay within the track even when the value exceeds
// 100% (the analysis load can), so an overloaded metric pins to the right edge
// instead of overflowing the card.
const barWidth = computed(() => (props.bar ? Math.min(Math.max(props.bar.value, 0), 100) : 0))

const trackStyle = computed(() => {
  if (!props.bar) return {}
  const threshold = props.bar.threshold
  const okColor = 'rgba(var(--admin-accent-rgb), 0.45)'
  const alertColor = 'rgba(var(--admin-danger-rgb), 0.55)'
  return {
    background: `linear-gradient(to right, ${okColor} ${threshold}%, ${alertColor} ${threshold}%)`,
  }
})
</script>

<style scoped>
.status-card {
  position: relative;
  background-color: var(--status-card-bg);
  border: 1px solid var(--status-card-border);
  border-radius: 8px;
  padding: 1.25rem;
}
.status-card.is-alert {
  border-color: var(--admin-danger);
  border-width: 2px;
  background-color: var(--status-card-alert-bg);
  box-shadow: 0 0 12px rgba(var(--admin-danger-rgb), 0.35);
}
.alert-icon {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  color: var(--admin-danger);
  font-size: 1rem;
}
.status-icon {
  font-size: 1.5rem;
  color: var(--admin-accent);
  margin-bottom: 0.5rem;
}
.status-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgba(255, 255, 255, 0.45);
  margin-bottom: 0.25rem;
}
.status-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}
.status-sub {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 0.25rem;
}
.status-unavailable {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.4);
  font-style: italic;
}
.progress {
  position: relative;
  height: 8px;
  border-radius: 4px;
  overflow: visible;
}
.progress-bar {
  border-radius: 2px;
  transition: width 0.4s ease;
}
.threshold-marker {
  position: absolute;
  top: -3px;
  bottom: -3px;
  width: 2px;
  background: rgba(255, 255, 255, 0.75);
  border-radius: 1px;
  transform: translateX(-50%);
}
</style>
