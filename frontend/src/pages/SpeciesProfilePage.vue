<template>
  <div class="container pb-5">
    <SpeciesProfile :species-slug="speciesSlug" :initial-selection="initialSelection" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import SpeciesProfile from '../components/species/SpeciesProfile.vue'
import { usePeriodSelection } from '../composables/usePeriodSelection.js'

const route = useRoute()

const speciesSlug = computed(() => route.params.slug)
const initialSelection = usePeriodSelection().resolveInitialSelection('7d')
</script>
