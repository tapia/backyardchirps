<template>
  <span class="confidence-badge" :class="level">{{ (confidence * 100).toFixed(0) }}%</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  confidence: { type: Number, required: true }, // 0..1
})

const level = computed(() => {
  const percentage = props.confidence * 100
  return percentage >= 75 ? 'high' : percentage >= 50 ? 'medium' : 'low'
})
</script>

<style scoped>
.confidence-badge {
  display: inline-block;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.68rem;
  line-height: 1.5;
  letter-spacing: 0.01em;
  padding: 1px 6px;
  border-radius: 1px;
  color: var(--sheet);
}
.confidence-badge.high {
  background: var(--confidence-high);
}
.confidence-badge.medium {
  background: var(--confidence-medium);
}
.confidence-badge.low {
  background: var(--confidence-low);
}
</style>
