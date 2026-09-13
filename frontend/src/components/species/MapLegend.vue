<template>
  <ul class="map-legend" :class="{ 'map-legend--overlay': overlay }">
    <li v-for="item in legendItems" :key="item.modifier" class="map-legend__item">
      <span class="map-legend__swatch" :class="`map-legend__swatch--${item.modifier}`"></span>
      <span class="map-legend__label">{{ t(item.labelKey) }}</span>
    </li>
  </ul>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  // Laid over the expanded (full-screen) map, with larger swatches and type.
  // Without it the legend is a strip in the normal flow, under the preview.
  overlay: { type: Boolean, default: false },
})

const { t } = useI18n()

// Seasonal range categories. Each swatch colour comes from its --range-* CSS
// variable via the modifier class.
const legendItems = [
  { modifier: 'breeding', labelKey: 'map.legendBreeding' },
  { modifier: 'nonbreeding', labelKey: 'map.legendNonBreeding' },
  { modifier: 'migration', labelKey: 'map.legendMigration' },
  { modifier: 'resident', labelKey: 'map.legendResident' },
]
</script>

<style scoped>
.map-legend {
  margin: 0;
  padding: 0.4rem 0.6rem;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem 0.75rem;
  border-top: 1px solid var(--border-soft);
  font-size: 0.68rem;
  line-height: 1.2;
  color: var(--graphite);
}
/* Pinned to the bottom-left of the full-screen backdrop. Clicks fall through,
   so a click on the legend still closes the lightbox. */
.map-legend--overlay {
  position: absolute;
  left: 1rem;
  bottom: 1rem;
  padding: 0.5rem 0.7rem;
  display: grid;
  gap: 0.25rem;
  border-top: none;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  font-size: 0.8rem;
  pointer-events: none;
}
.map-legend__item {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
}
.map-legend__swatch {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 3px;
}
.map-legend--overlay .map-legend__swatch {
  width: 13px;
  height: 13px;
}
.map-legend__swatch--breeding {
  background: var(--range-breeding);
}
.map-legend__swatch--nonbreeding {
  background: var(--range-nonbreeding);
}
.map-legend__swatch--migration {
  background: var(--range-migration);
}
.map-legend__swatch--resident {
  background: var(--range-resident);
}
</style>
