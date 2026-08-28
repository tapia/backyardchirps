<template>
  <span
    v-if="validated"
    class="confidence-badge validated"
    v-bs-tooltip="t('detection.validatedHint')"
  >
    <i class="bi bi-check2 me-1"></i>{{ t('detection.validated') }}
  </span>
  <span v-else class="confidence-badge">{{ (confidence * 100).toFixed(0) }}%</span>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

// A detection a person has checked shows no number. Once someone has decided, the
// model's score says nothing more, and after a reassignment it was the score for a
// different species altogether.
defineProps({
  confidence: { type: Number, required: true }, // 0..1
  validated: { type: Boolean, default: false },
})

const { t } = useI18n()
</script>

<style scoped>
.confidence-badge {
  display: inline-block;
  font-family: var(--font-sans);
  font-size: 0.68rem;
  line-height: 1.5;
  letter-spacing: 0.01em;
  padding: 1px 6px;
  border-radius: 1px;
  color: var(--sheet);
  background: var(--confidence-badge);
  white-space: nowrap;
}
.confidence-badge.validated {
  background: var(--confidence-validated);
}
</style>
