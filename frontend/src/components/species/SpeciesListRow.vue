<template>
  <RouterLink
    :to="to"
    class="list-item d-flex align-items-center gap-2 px-3 py-2 text-reset text-decoration-none"
  >
    <img
      :src="species.image_url"
      :alt="species.common_name"
      class="list-item__img flex-shrink-0 rounded"
      @error="$event.target.style.display = 'none'"
    />
    <div class="flex-grow-1 overflow-hidden">
      <span class="bird-name">{{ species.common_name }}</span>
      <span class="scientific-name d-block d-sm-inline ms-0 ms-sm-2">{{
        species.scientific_name
      }}</span>
    </div>
    <div class="flex-shrink-0 text-end meta">
      <template v-if="showPeriod">
        <span class="meta-pair">
          <span class="meta-label">{{ periodLabel }}</span>
          <span class="meta-count">{{ species.count_in_period?.toLocaleString() }}</span>
        </span>
        <span class="sep">·</span>
      </template>
      <span class="meta-pair">
        <span class="meta-label">{{ t('common.total') }}</span>
        <span :class="showPeriod ? 'meta-count--muted' : 'meta-count'">{{
          species.count_total?.toLocaleString()
        }}</span>
      </span>
    </div>
    <button
      v-if="chartToggle"
      class="chart-btn flex-shrink-0"
      :class="{ active: selected }"
      v-bs-tooltip="selected ? t('chart.removeFromChart') : t('chart.addToChart')"
      @click.stop.prevent="$emit('toggle')"
    >
      <i class="bi bi-graph-up"></i>
    </button>
  </RouterLink>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
defineProps({
  species: Object,
  to: { type: [Object, String], required: true },
  periodLabel: String,
  showPeriod: Boolean,
  chartToggle: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})
defineEmits(['toggle'])
</script>

<style scoped>
.list-item {
  cursor: pointer;
  border-bottom: 1px solid var(--limestone);
  padding-top: 0.65rem;
  padding-bottom: 0.65rem;
  transition: background 0.1s;
}
.list-item:hover {
  background: var(--lichen-pale);
}

.list-item__img {
  width: 52px;
  height: 52px;
  object-fit: cover;
  border-radius: 1px;
}

.bird-name {
  font-family: var(--font-serif);
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--graphite);
}
.scientific-name {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.8rem;
  color: var(--slate);
}

.meta {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  font-family: var(--font-sans);
  font-size: 0.8rem;
  color: var(--slate);
  white-space: nowrap;
}

/* On phones the period and total totals stack vertically to leave the species
   name more horizontal room. */
@media (max-width: 575.98px) {
  .meta {
    flex-direction: column;
    align-items: flex-end;
    gap: 0.05rem;
  }
  .meta .sep {
    display: none;
  }
}
.meta-pair {
  display: inline-flex;
  align-items: baseline;
  gap: 0.35em;
}
.meta-label {
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--slate);
}
.meta-count {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--graphite);
}
.meta-count--muted {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--slate);
}
.sep {
  margin: 0 0.4em;
  color: var(--limestone);
}

.chart-btn {
  background: none;
  border: 1px solid var(--limestone);
  border-radius: 2px;
  padding: 0.2rem 0.45rem;
  color: var(--slate);
  font-size: 0.8rem;
  line-height: 1;
  transition:
    border-color 0.1s,
    color 0.1s;
}
.chart-btn:hover {
  color: var(--lichen);
  border-color: var(--lichen);
  background: none;
}
.chart-btn.active {
  background: var(--lichen);
  color: var(--sheet);
  border-color: var(--lichen);
}
</style>
