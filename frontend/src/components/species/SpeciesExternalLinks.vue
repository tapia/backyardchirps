<template>
  <div class="hero-links d-flex flex-wrap gap-1">
    <a
      v-if="links?.wikipedia"
      :href="links.wikipedia"
      target="_blank"
      rel="noopener noreferrer"
      class="hero-link"
      v-bs-tooltip="'Wikipedia'"
    >
      <i class="bi bi-wikipedia hero-link-glyph"></i>
      <span class="hero-link-label">Wikipedia</span>
    </a>
    <a
      v-if="links?.ebird"
      :href="links.ebird"
      target="_blank"
      rel="noopener noreferrer"
      class="hero-link"
      v-bs-tooltip="'eBird'"
    >
      <img src="/icons/ebird.png" alt="eBird" class="hero-link-icon" />
      <span class="hero-link-label">eBird</span>
    </a>
    <a
      v-if="links?.seo"
      :href="links.seo"
      target="_blank"
      rel="noopener noreferrer"
      class="hero-link"
      v-bs-tooltip="'SEO/BirdLife'"
    >
      <img src="/icons/seo.png" alt="SEO/BirdLife" class="hero-link-icon" />
      <span class="hero-link-label">SEO/BirdLife</span>
    </a>
  </div>
</template>

<script setup>
defineProps({
  links: { type: Object, default: null },
})
</script>

<style scoped>
.hero-links {
  flex-wrap: wrap;
}
.hero-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  min-height: 24px;
  padding: 0 0.45rem;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  text-decoration: none;
  color: var(--slate);
  font-size: 0.7rem;
  font-weight: 500;
  opacity: 0.85;
  transition:
    border-color 0.12s,
    background 0.12s,
    color 0.12s,
    opacity 0.12s;
}
.hero-link:hover {
  border-color: var(--lichen);
  background: var(--lichen-pale);
  color: var(--graphite);
  opacity: 1;
}
.hero-link-glyph {
  font-size: 0.85rem;
}
.hero-link-icon {
  max-width: 32px;
  max-height: 13px;
  object-fit: contain;
  display: block;
}
</style>
