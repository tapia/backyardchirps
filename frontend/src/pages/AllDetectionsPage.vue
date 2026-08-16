<template>
  <div class="container pb-5">
    <h1 class="page-title">{{ t('page.allDetections.title') }}</h1>
    <p class="page-subtitle">{{ t('page.allDetections.subtitle') }}</p>

    <div class="filters">
      <div class="filter filter--species">
        <label class="filter-label">{{ t('page.allDetections.filterSpecies') }}</label>
        <div v-if="selectedSpecies" class="species-chip">
          <img
            v-if="selectedSpecies.image_url"
            :src="selectedSpecies.image_url"
            :alt="selectedSpecies.common_name || selectedSpecies.scientific_name"
            class="species-chip__img"
            @error="$event.target.style.display = 'none'"
          />
          <span class="species-chip__name" :class="{ 'species-sci': !selectedSpecies.common_name }">
            {{ selectedSpecies.common_name || selectedSpecies.scientific_name }}
          </span>
          <button
            type="button"
            class="species-chip__clear"
            :aria-label="t('page.allDetections.clearSpecies')"
            v-bs-tooltip="t('page.allDetections.clearSpecies')"
            @click="clearSpecies"
          >
            <i class="bi bi-x-lg"></i>
          </button>
        </div>
        <SpeciesSearchPicker v-else small floating @select="onSpeciesSelect" />
      </div>

      <div class="filter">
        <label class="filter-label">{{ t('filter.period') }}</label>
        <PeriodPicker :initial-selection="initialPeriodSelection" @change="onPeriodChange" />
      </div>
    </div>

    <div v-if="loading && !detections.length" class="text-center py-5 text-warm-muted">
      <div class="spinner-border"></div>
    </div>

    <div v-else-if="!detections.length" class="text-warm-muted text-center py-5">
      {{ hasActiveFilters ? t('page.allDetections.noMatches') : t('page.allDetections.empty') }}
    </div>

    <template v-else>
      <div class="table-scroll">
        <table class="detections-table">
          <thead>
            <tr>
              <th>{{ t('page.allDetections.time') }}</th>
              <th>{{ t('page.allDetections.saved') }}</th>
              <th>{{ t('page.allDetections.birdnetList') }}</th>
              <th class="num">{{ t('page.allDetections.processingTime') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="detection in detections"
              :key="detection.id"
              class="detection-row"
              role="link"
              tabindex="0"
              :aria-label="t('page.allDetections.view')"
              @click="goToRecording(detection.id)"
              @keydown.enter="goToRecording(detection.id)"
              @keydown.space.prevent="goToRecording(detection.id)"
            >
              <td class="time">{{ formatDateTime(detection.recorded_at) }}</td>
              <td class="saved">
                <div class="saved-inner">
                  <span
                    class="species-name"
                    :class="{ 'species-sci': !detection.species.common_name }"
                  >
                    {{ detection.species.common_name || detection.species.scientific_name }}
                  </span>
                  <ConfidenceBadge :confidence="detection.confidence" />
                </div>
              </td>
              <td class="candidates">
                <ul v-if="detection.candidates.length" class="candidate-list">
                  <li
                    v-for="(candidate, index) in detection.candidates"
                    :key="`${candidate.label}-${index}`"
                    class="candidate-item"
                  >
                    <span class="species-name" :class="{ 'species-sci': !candidate.common_name }">
                      {{ candidate.common_name || candidate.scientific_name || candidate.label }}
                    </span>
                    <ConfidenceBadge :confidence="candidate.confidence" />
                  </li>
                </ul>
                <span v-else class="text-warm-muted">n/a</span>
              </td>
              <td class="num">
                <span v-if="detection.analysis_time_ms != null">
                  {{ detection.analysis_time_ms }} ms
                </span>
                <span v-else class="text-warm-muted">n/a</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="load-more-row">
        <span class="count">
          {{ t('page.allDetections.showing', { shown: detections.length, total }) }}
        </span>
        <button
          v-if="detections.length < total"
          class="btn btn-outline-primary btn-sm"
          :disabled="loading"
          @click="loadMore"
        >
          {{ t('page.allDetections.loadMore') }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { fetchAllDetections } from '../api/index.js'
import ConfidenceBadge from '../components/common/ConfidenceBadge.vue'
import PeriodPicker from '../components/common/PeriodPicker.vue'
import SpeciesSearchPicker from '../components/species/SpeciesSearchPicker.vue'
import { usePeriodSelection } from '../composables/usePeriodSelection.js'
import { formatDateTime } from '../dates.js'
import { recordingRoute } from '../links.js'

const PAGE_SIZE = 50

const { t } = useI18n()
const router = useRouter()
const lang = inject('lang')

function goToRecording(detectionId) {
  router.push(recordingRoute(detectionId))
}

const detections = ref([])
const total = ref(0)
const loading = ref(false)

// Active filters. `selectedSpecies` is a taxonomy result object (or null); the
// date bounds are ISO strings (or null) emitted by the shared PeriodPicker,
// which also restores the window last chosen on any page.
const selectedSpecies = ref(null)
const start = ref(null)
const end = ref(null)
const initialPeriodSelection = usePeriodSelection().restoreSelection('24h')

const hasActiveFilters = computed(() => !!(selectedSpecies.value || start.value || end.value))

function onSpeciesSelect(species) {
  selectedSpecies.value = species
}

function clearSpecies() {
  selectedSpecies.value = null
}

// The picker emits the restored window on mount, which triggers the first load;
// later period changes reload from the first page too.
function onPeriodChange({ start: windowStart, end: windowEnd }) {
  start.value = windowStart || null
  end.value = windowEnd || null
  load(0)
}

async function load(offset) {
  loading.value = true
  try {
    const data = await fetchAllDetections({
      lang: lang.value,
      offset,
      limit: PAGE_SIZE,
      species: selectedSpecies.value?.scientific_name || undefined,
      start: start.value || undefined,
      end: end.value || undefined,
    })
    total.value = data.total
    if (offset === 0) {
      detections.value = data.detections
    } else {
      detections.value = detections.value.concat(data.detections)
    }
  } finally {
    loading.value = false
  }
}

function loadMore() {
  load(detections.value.length)
}

// A species filter change restarts the list from the first page. Period changes
// reload through onPeriodChange instead.
watch(selectedSpecies, () => load(0))
</script>

<style scoped>
.page-title {
  font-family: var(--font-serif);
  font-size: 1.4rem;
  color: var(--graphite);
  margin-top: 1rem;
}
.page-subtitle {
  font-family: var(--font-sans);
  font-size: 0.85rem;
  color: var(--warm-muted);
  margin-bottom: 1rem;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
  margin-bottom: 1.25rem;
}
.filter {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.filter--species {
  flex: 1 1 260px;
  min-width: 220px;
  max-width: 360px;
}
.filter-label {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--warm-muted);
  font-weight: 600;
}

.species-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px 4px 4px;
  border: 1px solid var(--dust);
  border-radius: 2px;
  background: var(--sheet);
  min-height: 33px;
}
.species-chip__img {
  width: 26px;
  height: 26px;
  object-fit: cover;
  border-radius: 1px;
  flex-shrink: 0;
}
.species-chip__name {
  font-family: var(--font-serif);
  font-size: 0.85rem;
  color: var(--graphite);
  flex-grow: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.species-chip__clear {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  padding: 0.2rem;
  color: var(--slate);
  font-size: 0.75rem;
  line-height: 1;
  flex-shrink: 0;
}
.species-chip__clear:hover {
  color: var(--graphite);
}

.table-scroll {
  overflow-x: auto;
}
.detections-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-sans);
  font-size: 0.85rem;
}
.detections-table th {
  text-align: left;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--warm-muted);
  font-weight: 600;
  padding: 6px 12px;
  border-bottom: 1px solid var(--warm-border);
  white-space: nowrap;
}
.detections-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--warm-border);
  vertical-align: middle;
}
.detections-table th.num,
.detections-table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.detection-row {
  cursor: pointer;
}
.detection-row:hover,
.detection-row:focus-visible {
  background: var(--lichen-pale);
  outline: none;
}
.time {
  color: var(--graphite);
  white-space: nowrap;
}
.detections-table td.saved {
  vertical-align: top;
}
.detections-table td.candidates {
  vertical-align: top;
}
.saved-inner {
  display: flex;
  align-items: center;
  gap: 8px;
}
.species-name {
  font-family: var(--font-serif);
  color: var(--graphite);
}
.species-sci {
  font-style: italic;
  color: var(--warm-muted);
}
.candidate-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.candidate-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 0;
}
.candidate-item:first-child {
  padding-top: 0;
}
.candidate-item + .candidate-item {
  border-top: 1px solid var(--warm-border);
}

.load-more-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 1rem;
}
.count {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  color: var(--warm-muted);
}
</style>
