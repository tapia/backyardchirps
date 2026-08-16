<template>
  <ImageLightbox
    v-if="lightboxOpen"
    :src="species.image_url"
    :alt="species.common_name"
    @close="lightboxOpen = false"
  />

  <div class="row g-3 g-md-4 mb-4 align-items-start align-items-lg-stretch">
    <!-- Column 1: illustration -->
    <div class="col-md-5">
      <div class="species-img-wrap" @click="lightboxOpen = true">
        <img
          :src="species.image_url"
          :alt="species.common_name"
          class="w-100 species-img"
          @error="$event.target.style.display = 'none'"
        />
        <span class="species-img-zoom" aria-hidden="true">
          <i class="bi bi-zoom-in"></i>
        </span>
      </div>
    </div>

    <div class="col-md-7">
      <div class="hero-cols">
        <!-- Column 2: common name, scientific name, links, KPIs -->
        <div class="hero-col-main">
          <div class="name-row">
            <h1 class="species-name mb-0">
              {{ species.common_name ?? species.scientific_name }}
            </h1>
            <!-- A blacklisted species reports has_detections: false but must keep
                 its detection rules reachable so it can be un-blacklisted. -->
            <SpeciesActionsMenu
              ref="actionsMenu"
              :species-slug="speciesSlug"
              :common-name="species.common_name ?? species.scientific_name"
              :allow-detection-rules="species.has_detections || hasCustomization"
              :detection-settings="detectionSettings"
              @settings-updated="onSettingsUpdated"
            />
          </div>
          <div class="sci-name fst-italic text-warm-muted">{{ species.scientific_name }}</div>
          <SpeciesExternalLinks :links="species.external_links" class="mt-2" />

          <!-- Detection status: compact badge (all users) + Edit action (admins). -->
          <div v-if="hasCustomization" class="detection-status">
            <SpeciesDetectionBadge :detection-settings="detectionSettings" />
            <button
              v-if="isStaff"
              type="button"
              class="detection-status__edit"
              @click="actionsMenu?.openSettings()"
            >
              {{ t('detectionSettings.edit') }}
            </button>
          </div>

          <!-- KPIs on desktop only; on mobile they live in the Info tab. -->
          <SpeciesKpiCards
            class="hero-kpis d-none d-lg-flex"
            :species="species"
            :species-slug="speciesSlug"
            :highlights="highlights"
            :period-label="periodLabel"
          />
        </div>

        <!-- Column 3: presence (map + seasonality), desktop only. -->
        <div v-if="hasMap" class="hero-col-side d-none d-lg-flex">
          <SpeciesPresence
            class="hero-side-presence"
            :species="species"
            :species-slug="speciesSlug"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ImageLightbox from '../common/ImageLightbox.vue'
import SpeciesExternalLinks from './SpeciesExternalLinks.vue'
import SpeciesKpiCards from './SpeciesKpiCards.vue'
import SpeciesPresence from './SpeciesPresence.vue'
import SpeciesActionsMenu from './SpeciesActionsMenu.vue'
import SpeciesDetectionBadge from './SpeciesDetectionBadge.vue'
import { useAuth } from '../../composables/useAuth.js'

const props = defineProps({
  species: { type: Object, required: true },
  speciesSlug: { type: String, required: true },
  highlights: { type: Array, default: null },
  periodLabel: { type: String, default: null },
  detectionSettings: {
    type: Object,
    default: () => ({ blacklisted: false, auto_confirm_threshold: null }),
  },
})

const emit = defineEmits(['settings-updated'])

const { t } = useI18n()
const { currentUser } = useAuth()

const lightboxOpen = ref(false)
const hasMap = computed(() => Boolean(props.species.map_url))

const isStaff = computed(() => Boolean(currentUser.value?.is_staff))
const hasCustomization = computed(
  () =>
    props.detectionSettings.blacklisted || props.detectionSettings.auto_confirm_threshold !== null,
)

const actionsMenu = ref(null)

function onSettingsUpdated() {
  emit('settings-updated')
}
</script>

<style scoped>
.species-name {
  font-family: var(--font-serif);
  font-size: 2rem;
  font-weight: 500;
  letter-spacing: -0.01em;
  line-height: 1.1;
}
.sci-name {
  font-family: var(--font-serif);
  font-size: 1.1rem;
}
.name-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}
.name-row .species-name {
  min-width: 0;
}

/* ── Detection status badge + Edit ───────────────────────────────── */
.detection-status {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
.detection-status__edit {
  border: none;
  background: none;
  padding: 0.1rem 0.2rem;
  color: var(--lichen);
  font-size: 0.85rem;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}
.detection-status__edit:hover {
  color: var(--lichen-dark);
}
.species-img-wrap {
  position: relative;
  cursor: zoom-in;
}
.species-img {
  border-radius: 1rem;
  background-color: #ffffff;
  display: block;
  aspect-ratio: 4 / 3;
  object-fit: contain;
  cursor: zoom-in;
}
/* Magnifying glass affordance, matching the map card's zoom badge. */
.species-img-zoom {
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
  pointer-events: none;
  transition:
    background 0.12s,
    color 0.12s;
}
.species-img-wrap:hover .species-img-zoom {
  background: #ffffff;
  color: var(--graphite);
}

/* ── Hero columns 2 (identity + KPIs) and 3 (share + presence) ────── */
.hero-cols {
  display: flex;
  gap: 1rem;
  align-items: stretch;
}
.hero-col-main {
  flex: 1 1 auto;
  min-width: 0;
}
.hero-col-side {
  flex: 0 0 240px;
  flex-direction: column;
  gap: 0.5rem;
}
@media (max-width: 991.98px) {
  .hero-cols {
    display: block;
  }
}
@media (min-width: 992px) {
  /* Column 2: name/sci/links stay tight at the top, KPIs drop to the bottom so
     they bottom-align with the map/seasonality in column 3. */
  .hero-col-main {
    display: flex;
    flex-direction: column;
  }
  .hero-col-main > .hero-kpis {
    margin-top: auto;
  }
  /* Column 3: share pinned top-right, presence dropped to the bottom. */
  .hero-col-side > .hero-side-presence {
    margin-top: auto;
  }
  /* The columns stretch to equal height, so the illustration is taken out of
     flow (absolute) and fills its column, its bottom lining up with the KPIs. */
  .species-img-wrap {
    height: 100%;
  }
  .species-img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    aspect-ratio: auto;
  }
}

@media (max-width: 767px) {
  .species-name {
    font-size: 1.55rem;
  }
  .sci-name {
    font-size: 1rem;
  }
}
</style>
