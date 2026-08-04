<template>
  <div
    class="map-card"
    role="button"
    tabindex="0"
    :aria-label="t('map.openFull')"
    @click="lightboxOpen = true"
    @keydown.enter="lightboxOpen = true"
    @keydown.space.prevent="lightboxOpen = true"
  >
    <img :src="mapUrl" :alt="alt" class="map-card__img" />
    <span class="map-card__zoom" aria-hidden="true">
      <i class="bi bi-zoom-in"></i>
    </span>

    <MapLegend />

    <!-- Teleports to body, so its place in the tree doesn't affect the card;
         keeping it inside gives the component a single root so a passed-in
         class (e.g. d-lg-none) is inherited by the card element. The legend is
         repeated over the expanded image so it stays visible when zoomed in. -->
    <ImageLightbox v-if="lightboxOpen" :src="mapUrl" :alt="alt" @close="lightboxOpen = false">
      <MapLegend large />
    </ImageLightbox>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ImageLightbox from '../common/ImageLightbox.vue'
import MapLegend from './MapLegend.vue'

defineProps({
  mapUrl: { type: String, required: true },
  alt: { type: String, default: '' },
})

const { t } = useI18n()
const lightboxOpen = ref(false)
</script>

<style scoped>
.map-card {
  position: relative;
  display: block;
  width: 100%;
  padding: 0;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  overflow: hidden;
  background: var(--sheet);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
  cursor: zoom-in;
  /* Always a square preview, whatever width the container gives it. */
  aspect-ratio: 1 / 1;
  transition:
    border-color 0.12s,
    box-shadow 0.12s;
}
.map-card:hover {
  border-color: var(--limestone);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.map-card:focus-visible {
  outline: 2px solid var(--lichen);
  outline-offset: 2px;
}

.map-card__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* Subtle magnifying glass affordance in the top-right corner. */
.map-card__zoom {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--slate);
  font-size: 0.9rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  transition:
    background 0.12s,
    color 0.12s;
}
.map-card:hover .map-card__zoom {
  background: #ffffff;
  color: var(--graphite);
}
</style>
