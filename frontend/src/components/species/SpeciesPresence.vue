<template>
  <div class="species-presence">
    <SpeciesMapCard :map-url="species.map_url" :alt="mapAlt" />
    <SeasonalityChart :species-slug="speciesSlug" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SpeciesMapCard from './SpeciesMapCard.vue'
import SeasonalityChart from '../charts/SeasonalityChart.vue'

const props = defineProps({
  species: { type: Object, required: true },
  speciesSlug: { type: String, required: true },
})

const mapAlt = computed(() => props.species.common_name ?? props.species.scientific_name)
</script>

<style scoped>
/* Where (map) stacked over when (seasonality). */
.species-presence {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>
