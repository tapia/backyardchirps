<template>
  <ul class="map-legend" :class="{ 'map-legend--large': large }">
    <li v-for="item in legendItems" :key="item.modifier" class="map-legend__item">
      <span class="map-legend__swatch" :class="`map-legend__swatch--${item.modifier}`"></span>
      <span class="map-legend__label">{{ t(item.labelKey) }}</span>
    </li>
  </ul>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  // Larger swatches/type for the expanded (full-screen) map.
  large: { type: Boolean, default: false },
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
/* Pinned to the bottom-left of the nearest positioned ancestor: the map card in
   the preview, or the full-screen backdrop when expanded. */
.map-legend {
  position: absolute;
  left: 0.5rem;
  bottom: 0.5rem;
  margin: 0;
  padding: 0.35rem 0.5rem;
  list-style: none;
  display: grid;
  gap: 0.15rem;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  font-size: 0.62rem;
  line-height: 1.2;
  color: var(--graphite);
  /* Let clicks fall through so the map's own click handling still works. */
  pointer-events: none;
}
.map-legend--large {
  left: 1rem;
  bottom: 1rem;
  padding: 0.5rem 0.7rem;
  gap: 0.25rem;
  font-size: 0.8rem;
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
.map-legend--large .map-legend__swatch {
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
