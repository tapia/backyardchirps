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

      <!-- Period filter. Hidden rather than removed on the other tabs, so the picker keeps
           a period moved back in time when you return. -->
      <div
        v-show="activeTab === 'detections'"
        class="period-bar d-flex align-items-center flex-wrap gap-2 gap-sm-3 mb-4"
      >
        <span class="stat-label d-none d-sm-inline">{{ t('filter.period') }}</span>
        <PeriodPicker
          :initial-selection="selection"
          :emit-on-mount="false"
          @change="onPeriodChange"
        />
      </div>

      <template v-if="activeTab === 'detections'">
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
import { formatShortDateRange } from '../../dates.js'
import {
  findPreset,
  normalizeSelection,
  presetWindow,
  selectionWindow,
} from '../../periodPresets.js'

const props = defineProps({
  speciesSlug: { type: String, required: true },
  // Time-range selection to start from: { preset } or { preset: 'custom', range }.
  initialSelection: { type: Object, default: () => ({ preset: '7d' }) },
})

const { t, locale } = useI18n()
const lang = inject('lang')

const detectionSettings = computed(
  () => species.value?.detection_settings ?? { blacklisted: false, auto_confirm_threshold: null },
)
const blacklisted = computed(() => detectionSettings.value.blacklisted)

const species = ref(null)
const chartData = ref(null)
const highlightsHourly = ref(null)
const loading = ref(false)
// The first data load happens before the picker exists (it is part of the loaded
// profile), so the starting window is worked out here and the picker does not emit it.
// `selection` follows what the user picks, so the picker rebuilt for another species
// starts from it.
const selection = ref(normalizeSelection(props.initialSelection, '7d'))
const start = ref(null)
const end = ref(null)
const currentPreset = ref(null)
showSelectionWindow()
const activeTab = ref('detections')
const recordingsSort = ref('newest')

function onPeriodChange({ preset, start: newStart, end: newEnd, selection: newSelection }) {
  currentPreset.value = preset
  start.value = newStart
  end.value = newEnd
  selection.value = newSelection
}

function showSelectionWindow() {
  const selectedWindow = selectionWindow(selection.value)
  currentPreset.value = selection.value.preset
  start.value = selectedWindow.start.toISOString()
  end.value = selectedWindow.end ? selectedWindow.end.toISOString() : null
}

// Human-readable label for the active period, shown under the detections
// hero stat so the count is not mistaken for an all-time total.
const heroPeriodLabel = computed(() => {
  const preset = findPreset(currentPreset.value)
  if (preset) return t(preset.labelKey)
  return formatShortDateRange(start.value, end.value, locale.value)
})

// Hero highlights are period-independent: derived from the last year of data
// (year-scoped hourly counts + the yearly daily counts already fetched for the
// calendar chart), so they read as a stable summary of the species' behavior.
const highlights = computed(() =>
  highlightsHourly.value && chartData.value
    ? deriveSpeciesHighlights({ hourly: highlightsHourly.value, daily: chartData.value.yearly })
    : null,
)

async function _fetchHighlightsHourly() {
  const lastYear = presetWindow(findPreset('1y'), 0)
  return api.fetchDetectionsPerHourOfDay(props.speciesSlug, { start: lastYear.start.toISOString() })
}

// While load() runs it already fetches with the current window, so a window change it
// caused (see the species watch below) must not start a second fetch.
watch([start, end, locale], () => {
  if (!loading.value) reloadSpeciesAndCharts()
})

watch(
  () => props.speciesSlug,
  () => {
    // Keep the selected period when switching species, but not a period moved back in
    // time: the picker is rebuilt with the new profile and starts from the selection.
    activeTab.value = 'detections'
    recordingsSort.value = 'newest'
    showSelectionWindow()
    load()
  },
)

async function onSettingsUpdated() {
  await loadSpeciesData()
}

function _filterParams() {
  return { start: start.value, end: end.value }
}

async function _fetchSpeciesDetail() {
  return api.fetchSpeciesDetail(props.speciesSlug, { lang: lang.value, ..._filterParams() })
}

async function _fetchChartData() {
  const params = _filterParams()
  const [hourly, heatmap, yearly] = await Promise.all([
    api.fetchDetectionsPerHourOfDay(props.speciesSlug, params),
    api.fetchDetectionsHeatmap(props.speciesSlug, params),
    api.fetchDetectionsPerDayOverLastYear(props.speciesSlug),
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
