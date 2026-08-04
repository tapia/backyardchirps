<template>
  <div v-if="loading" class="text-center py-5 text-warm-muted">
    <div class="spinner-border"></div>
  </div>

  <template v-else-if="species">
    <SpeciesProfileHeader
      :species="species"
      :species-slug="speciesSlug"
      :highlights="highlights"
      :period-label="heroPeriodLabel"
      :detection-settings="detectionSettings"
      @settings-updated="onSettingsUpdated"
    />

    <template v-if="species.has_detections">
      <!-- Tabs -->
      <ul class="nav nav-tabs nav-fill profile-tabs mb-4">
        <!-- Info tab holds the KPI cards + map on mobile only; on desktop that
             content lives in the hero, so this tab is hidden. -->
        <li class="nav-item d-lg-none">
          <button
            class="nav-link"
            :class="{ active: activeTab === 'info' }"
            @click="activeTab = 'info'"
          >
            <i class="bi bi-info-circle"></i>
            <span class="tab-label">{{ t('modal.tabInfo') }}</span>
          </button>
        </li>
        <li class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeTab === 'detections' }"
            @click="activeTab = 'detections'"
          >
            <i class="bi bi-bar-chart-line"></i>
            <span class="tab-label">{{ t('modal.tabDetections') }}</span>
          </button>
        </li>
        <li class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeTab === 'recordings' }"
            @click="activeTab = 'recordings'"
          >
            <i class="bi bi-mic"></i>
            <span class="tab-label"
              >{{ t('modal.tabRecordings') }}
              <span class="tab-count">{{ species.recordings_total }}</span></span
            >
          </button>
        </li>
        <li class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeTab === 'sounds' }"
            @click="activeTab = 'sounds'"
          >
            <i class="bi bi-music-note-beamed"></i>
            <span class="tab-label">{{ t('sound.title') }}</span>
          </button>
        </li>
      </ul>

      <template v-if="activeTab === 'detections'">
        <!-- Period filter -->
        <div class="period-bar d-flex align-items-center flex-wrap gap-2 gap-sm-3 mb-4">
          <span class="stat-label d-none d-sm-inline">{{ t('filter.period') }}</span>
          <PeriodPicker
            variant="primary"
            mobile-dropdown
            :default-preset="pickerDefaultPreset"
            :initial-range="pickerInitialRange"
            @change="onPeriodChange"
          />
        </div>

        <!-- Charts -->
        <template v-if="chartData">
          <div class="row g-3 mb-3">
            <div class="col-lg-7">
              <ActivityHeatmapChart
                :heatmap="chartData.heatmap"
                :x-labels="chartData.heatmapXLabels"
                :granularity="chartData.heatmapGranularity"
              />
            </div>
            <div class="col-lg-5">
              <HourOfDayPolarChart :hourly="chartData.hourly" />
            </div>
          </div>
          <DetectionsCalendarChart class="mb-3" :daily="chartData.yearly" />
        </template>
      </template>

      <SpeciesRecordingsTab
        v-else-if="activeTab === 'recordings'"
        v-model:sort="recordingsSort"
        :species-slug="speciesSlug"
        :species="species"
        @validated="loadSpeciesData"
      />

      <template v-else-if="activeTab === 'sounds'">
        <ReferenceCallList :sounds="species.sounds" />
      </template>

      <!-- Mobile-only overview; on desktop this content lives in the hero. -->
      <template v-else-if="activeTab === 'info'">
        <SpeciesKpiCards
          :species="species"
          :species-slug="speciesSlug"
          :highlights="highlights"
          :period-label="heroPeriodLabel"
        />
        <SpeciesPresence
          v-if="species.map_url"
          class="mt-3"
          :species="species"
          :species-slug="speciesSlug"
        />
      </template>
    </template>

    <div v-else class="stat-card-warm text-center py-4 text-warm-muted">
      <template v-if="blacklisted">
        <i class="bi bi-eye-slash me-1"></i>{{ t('modal.blacklistedNoData') }}
      </template>
      <template v-else> <i class="bi bi-info-circle me-1"></i>{{ t('modal.noData') }} </template>
    </div>
  </template>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '../../api/index.js'
import { deriveSpeciesHighlights } from '../../speciesHighlights.js'
import ActivityHeatmapChart from '../charts/ActivityHeatmapChart.vue'
import HourOfDayPolarChart from '../charts/HourOfDayPolarChart.vue'
import DetectionsCalendarChart from '../charts/DetectionsCalendarChart.vue'
import ReferenceCallList from '../recordings/ReferenceCallList.vue'
import PeriodPicker from '../common/PeriodPicker.vue'
import SpeciesProfileHeader from './SpeciesProfileHeader.vue'
import SpeciesKpiCards from './SpeciesKpiCards.vue'
import SpeciesPresence from './SpeciesPresence.vue'
import SpeciesRecordingsTab from './SpeciesRecordingsTab.vue'
import { useConfidenceFilter } from '../../composables/useConfidenceFilter.js'

const props = defineProps({
  speciesSlug: { type: String, required: true },
  // Time-range selection to start from: { preset } or { preset: 'custom', range }.
  initialSelection: { type: Object, default: () => ({ preset: '7d' }) },
})

const PRESET_DAYS = { '24h': 1, '7d': 7, '30d': 30, '1y': 365 }
const PRESET_PERIOD_LABEL_KEYS = {
  '24h': 'period.last24h',
  '7d': 'period.last7d',
  '30d': 'period.last30d',
  '1y': 'period.last1y',
}

function presetStartDate(preset) {
  const days = PRESET_DAYS[preset]
  if (!days) return null
  const date = new Date(Date.now() - (days - 1) * 24 * 60 * 60 * 1000)
  if (preset !== '24h') date.setHours(0, 0, 0, 0)
  return date.toISOString()
}

const { t, locale } = useI18n()
const lang = inject('lang')
const { confidenceLevel } = useConfidenceFilter()

const detectionSettings = computed(
  () => species.value?.detection_settings ?? { blacklisted: false, auto_confirm_threshold: null },
)
const blacklisted = computed(() => detectionSettings.value.blacklisted)

const species = ref(null)
const chartData = ref(null)
const highlightsHourly = ref(null)
const loading = ref(false)
// When the initial selection is a custom range, hand it to the picker so it
// highlights the custom window (and shows its dates) instead of a preset.
const initialCustomRange =
  props.initialSelection.preset === 'custom' && props.initialSelection.range?.length === 2
    ? props.initialSelection.range
    : null
const start = ref(
  initialCustomRange ? initialCustomRange[0] : presetStartDate(props.initialSelection.preset),
)
const end = ref(initialCustomRange ? initialCustomRange[1] : null)
const pickerDefaultPreset = ref(props.initialSelection.preset)
const pickerInitialRange = initialCustomRange
const currentPreset = ref(props.initialSelection.preset)
const activeTab = ref('detections')
const recordingsSort = ref('newest')

function onPeriodChange({ preset, start: newStart, end: newEnd }) {
  currentPreset.value = preset
  start.value = newStart || null
  end.value = newEnd || null
}

// Human-readable label for the active period, shown under the detections
// hero stat so the count is not mistaken for an all-time total.
const heroPeriodLabel = computed(() => {
  const labelKey = PRESET_PERIOD_LABEL_KEYS[currentPreset.value]
  if (labelKey) return t(labelKey)
  if (start.value && end.value) {
    return `${_formatShortDate(start.value)} – ${_formatShortDate(end.value)}`
  }
  return t('period.allTime')
})

function _formatShortDate(isoDate) {
  return new Date(isoDate).toLocaleDateString(locale.value, { month: 'short', day: 'numeric' })
}

// Hero highlights are period-independent: derived from the last year of data
// (year-scoped hourly counts + the yearly daily counts already fetched for the
// calendar chart), so they read as a stable summary of the species' behavior.
const highlights = computed(() =>
  highlightsHourly.value && chartData.value
    ? deriveSpeciesHighlights({ hourly: highlightsHourly.value, daily: chartData.value.yearly })
    : null,
)

async function _fetchHighlightsHourly() {
  return api.fetchDetectionsPerHourOfDay(props.speciesSlug, {
    start: presetStartDate('1y'),
    minConfidence: confidenceLevel.value,
  })
}

watch(confidenceLevel, async () => {
  if (species.value?.has_detections) {
    highlightsHourly.value = await _fetchHighlightsHourly()
  }
})

watch([start, end, confidenceLevel, locale], reloadSpeciesAndCharts)

watch(
  () => props.speciesSlug,
  () => {
    // Keep the currently selected period when switching species; only reset the
    // per-species view state and reload data for the new species.
    activeTab.value = 'detections'
    recordingsSort.value = 'newest'
    load()
  },
)

async function onSettingsUpdated() {
  await loadSpeciesData()
}

function _filterParams() {
  return { start: start.value, end: end.value, minConfidence: confidenceLevel.value }
}

async function _fetchSpeciesDetail() {
  return api.fetchSpeciesDetail(props.speciesSlug, { lang: lang.value, ..._filterParams() })
}

async function _fetchChartData() {
  const params = _filterParams()
  const [hourly, heatmap, yearly] = await Promise.all([
    api.fetchDetectionsPerHourOfDay(props.speciesSlug, params),
    api.fetchDetectionsHeatmap(props.speciesSlug, params),
    api.fetchDetectionsPerDayOverLastYear(props.speciesSlug, {
      minConfidence: confidenceLevel.value,
    }),
  ])
  return {
    hourly,
    heatmap: heatmap.heatmap,
    heatmapXLabels: heatmap.x_labels,
    heatmapGranularity: heatmap.granularity,
    yearly,
  }
}

async function reloadSpeciesAndCharts() {
  species.value = await _fetchSpeciesDetail()
  chartData.value = species.value.has_detections ? await _fetchChartData() : null
}

// Single source of truth for every data source the profile shows (species
// detail + charts + highlights). Both the initial page load and the
// post-validation refresh go through here, so adding a new data source only
// needs to be wired up once and neither path can show outdated data.
async function loadSpeciesData() {
  species.value = await _fetchSpeciesDetail()
  if (species.value.has_detections) {
    ;[chartData.value, highlightsHourly.value] = await Promise.all([
      _fetchChartData(),
      _fetchHighlightsHourly(),
    ])
  } else {
    chartData.value = null
    highlightsHourly.value = null
  }
}

async function load() {
  species.value = null
  chartData.value = null
  highlightsHourly.value = null
  loading.value = true
  try {
    await loadSpeciesData()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* ── Labeled tab navigation ──────────────────────────────────────── */
.nav-tabs.profile-tabs .nav-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  padding: 0.65rem 0.5rem;
  border-bottom-width: 3px;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}
.nav-tabs.profile-tabs .nav-link.active {
  background: rgba(var(--lichen-rgb), 0.07);
  border-bottom-color: var(--lichen);
}
.nav-tabs.profile-tabs .nav-link .bi {
  font-size: 1.05rem;
}
/* GitHub-style counter: neutral pill that picks up the active tab tint */
.tab-count {
  display: inline-block;
  min-width: 1.6em;
  padding: 0.05em 0.5em;
  border-radius: 999px;
  background: var(--limestone);
  color: var(--slate);
  font-size: 0.68rem;
  font-weight: 600;
  line-height: 1.5;
  text-align: center;
  vertical-align: 0.08em;
}
.nav-tabs.profile-tabs .nav-link.active .tab-count {
  background: rgba(var(--lichen-rgb), 0.16);
  color: var(--lichen-dark);
}

@media (max-width: 575px) {
  .nav-tabs.profile-tabs .nav-link {
    flex-direction: column;
    gap: 0.15rem;
    font-size: 0.72rem;
    padding: 0.5rem 0.25rem;
  }
}
</style>
