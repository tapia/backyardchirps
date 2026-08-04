<template>
  <RouterLink :to="to" class="card h-100 bird-card shadow-sm text-reset text-decoration-none">
    <img
      :src="species.image_url"
      :alt="species.common_name"
      class="card-img-top bird-card__img"
      @error="$event.target.style.display = 'none'"
    />
    <div class="card-body px-3 pt-3 pb-3">
      <h5 class="bird-name mb-0">{{ species.common_name }}</h5>
      <p class="scientific-name mb-0">{{ species.scientific_name }}</p>
      <hr class="card-divider" />
      <div class="d-flex align-items-end">
        <div class="d-flex gap-4 flex-grow-1">
          <div v-if="showPeriod">
            <div class="stat-label">{{ periodLabel }}</div>
            <div class="stat-value">{{ species.count_in_period?.toLocaleString() }}</div>
          </div>
          <div>
            <div class="stat-label">{{ t('common.total') }}</div>
            <div class="stat-value" :class="showPeriod ? 'stat-value--muted' : ''">
              {{ species.count_total?.toLocaleString() }}
            </div>
          </div>
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
      </div>
    </div>
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
.bird-card {
  cursor: pointer;
  transition: background 0.12s;
}
.bird-card:hover {
  background: var(--lichen-pale) !important;
}

.bird-card__img {
  height: 228px;
  object-fit: contain;
  border-radius: 0;
  background-color: #ffffff;
}

.bird-name {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1rem;
  font-weight: 500;
  color: var(--graphite);
}
.scientific-name {
  font-family: 'Newsreader', Georgia, serif;
  font-style: italic;
  font-size: 0.82rem;
  color: var(--slate);
  margin-top: 2px;
}

.card-divider {
  border: none;
  border-top: 1px solid var(--limestone);
  margin: 0.85rem 0 0.75rem;
  opacity: 1;
}

.stat-value {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--graphite);
  line-height: 1.1;
}
.stat-value--muted {
  color: var(--slate);
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
