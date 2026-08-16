<template>
  <div class="already-saved">
    <!-- The heading carries the status, so the rows are bare names. Nothing here
         is a control: these species are context for the recording, not choices. -->
    <div class="stat-label mb-1">{{ t('modal.alreadySavedHere') }}</div>
    <ul class="already-saved__list">
      <li v-for="entry in species" :key="entry.scientific_name" class="already-saved__item">
        <i class="bi bi-feather already-saved__mark" aria-hidden="true"></i>
        {{ entry.common_name }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  species: { type: Array, default: () => [] },
})
</script>

<style scoped>
.already-saved {
  margin-top: 14px;
}
/* A stack, bound by a soft rule down its left edge and marked with a feather
   per name. Enough to read as a deliberate group rather than loose lines,
   while staying unboxed and untinted so none of it looks like a control. */
.already-saved__list {
  list-style: none;
  margin: 0;
  padding: 2px 0 2px 12px;
  border-left: 2px solid rgba(var(--lichen-rgb), 0.35);
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.already-saved__item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-family: var(--font-serif);
  font-size: 0.95rem;
  color: var(--graphite);
  line-height: 1.45;
}
.already-saved__mark {
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--lichen);
}
</style>
