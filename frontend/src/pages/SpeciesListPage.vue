<template>
  <div class="container pb-5">
    <SpeciesListToolbar :sort="sort" @period-change="onPeriodChange" @update:sort="sort = $event" />

    <div v-if="loading" class="text-center py-5 text-warm-muted">
      <div class="spinner-border spinner-border-sm me-2"></div>
      {{ t('common.loading') }}
    </div>

    <template v-else>
      <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
        <div class="d-flex align-items-center flex-wrap gap-2 gap-sm-3">
          <div class="btn-group btn-group-sm">
            <button
              type="button"
              class="btn"
              :class="chartMode === 'timeline' ? 'btn-primary' : 'btn-outline-primary'"
              v-bs-tooltip="t('page.species.timelineChart')"
              :aria-label="t('page.species.timelineChart')"
              @click="setChartMode('timeline')"
            >
              <i class="bi bi-graph-up"></i>
            </button>
            <button
              type="button"
              class="btn"
              :class="chartMode === 'hourly' ? 'btn-primary' : 'btn-outline-primary'"
              v-bs-tooltip="t('page.species.hourlyChart')"
              :aria-label="t('page.species.hourlyChart')"
              @click="setChartMode('hourly')"
            >
              <i class="bi bi-grid-3x3-gap"></i>
            </button>
          </div>
          <div class="d-flex align-items-center gap-2">
            <span class="small text-warm-muted d-none d-sm-inline">{{
              t('page.species.chartSpeciesCount')
            }}</span>
            <div
              class="btn-group btn-group-sm"
              role="group"
              v-bs-tooltip="t('page.species.chartSpeciesCountHint')"
              :aria-label="t('page.species.chartSpeciesCountHint')"
            >
              <button
                v-for="count in chartSpeciesCountOptions"
                :key="count"
                type="button"
                class="btn"
                :class="chartSpeciesCount === count ? 'btn-primary' : 'btn-outline-primary'"
                @click="chartSpeciesCount = count"
              >
                {{ count }}
              </button>
            </div>
          </div>
        </div>
        <div v-if="canNavigate" class="btn-group btn-group-sm">
          <button
            type="button"
            class="btn btn-outline-secondary"
            v-bs-tooltip="t('period.prevPeriod')"
            :aria-label="t('period.prevPeriod')"
            @click="navigatePrev"
          >
            <i class="bi bi-chevron-left"></i>
          </button>
          <span class="btn btn-outline-secondary pe-none nav-period-label">{{
            navWindowLabel
          }}</span>
          <button
            type="button"
            class="btn btn-outline-secondary"
            :disabled="isAtPresent"
            v-bs-tooltip="t('period.nextPeriod')"
            :aria-label="t('period.nextPeriod')"
            @click="navigateNext"
          >
            <i class="bi bi-chevron-right"></i>
          </button>
          <button
            type="button"
            class="btn btn-outline-secondary"
            :disabled="isAtPresent"
            v-bs-tooltip="t('period.now')"
            :aria-label="t('period.now')"
            @click="goToNow"
          >
            <i class="bi bi-chevron-double-right"></i>
          </button>
        </div>
      </div>

      <template v-if="chartMode === 'timeline'">
        <SpeciesComparisonViolinChart
          v-if="chartSeries.length"
          :series="chartSeries"
          :granularity="chartGranularity"
          class="mb-3"
        />
        <div v-else class="stat-card-warm mb-3 chart-empty-placeholder">
          <span class="small text-warm-muted">{{ t('page.species.empty') }}</span>
        </div>
      </template>
      <template v-else>
        <SpeciesHourlyHeatmapChart
          v-if="hourlySpecies.length"
          :species="hourlySpecies"
          :days="hourlyDays"
          class="mb-3"
        />
        <div v-else class="stat-card-warm mb-3 chart-empty-placeholder">
          <span class="small text-warm-muted">{{ t('page.species.empty') }}</span>
        </div>
      </template>

      <div class="d-flex align-items-center justify-content-between mb-3">
        <span class="small text-warm-muted">{{
          t('page.species.detected', { n: species.length })
        }}</span>
        <div class="btn-group btn-group-sm">
          <button
            type="button"
            class="btn"
            :class="viewMode === 'grid' ? 'btn-primary' : 'btn-outline-primary'"
            @click="viewMode = 'grid'"
          >
            <i class="bi bi-grid"></i>
          </button>
          <button
            type="button"
            class="btn"
            :class="viewMode === 'list' ? 'btn-primary' : 'btn-outline-primary'"
            @click="viewMode = 'list'"
          >
            <i class="bi bi-list-ul"></i>
          </button>
        </div>
      </div>

      <template v-if="species.length > 0">
        <div
          v-if="viewMode === 'grid'"
          class="row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-lg-4 g-4"
        >
          <div v-for="s in species" :key="s.slug" class="col">
            <SpeciesGridCard
              :species="s"
              :period-label="periodLabel"
              :show-period="!!start"
              chart-toggle
              :selected="selectedSlugs.has(s.slug)"
              :to="speciesRoute(s.slug)"
              @toggle="toggleChart(s.slug)"
            />
          </div>
        </div>

        <div v-else class="species-list">
          <SpeciesListRow
            v-for="s in species"
            :key="s.slug"
            :species="s"
            :period-label="periodLabel"
            :show-period="!!start"
            chart-toggle
            :selected="selectedSlugs.has(s.slug)"
            :to="speciesRoute(s.slug)"
            @toggle="toggleChart(s.slug)"
          />
        </div>
      </template>
      <div v-else class="species-list-empty-placeholder">
        <div v-for="n in 6" :key="n" class="species-placeholder-row"></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '../api/index.js'
import { speciesRoute } from '../links.js'
import SpeciesListToolbar from '../components/species/SpeciesListToolbar.vue'
import SpeciesGridCard from '../components/species/SpeciesGridCard.vue'
import SpeciesListRow from '../components/species/SpeciesListRow.vue'
import SpeciesComparisonViolinChart from '../components/charts/SpeciesComparisonViolinChart.vue'
import SpeciesHourlyHeatmapChart from '../components/charts/SpeciesHourlyHeatmapChart.vue'
import { readChartMode, writeChartMode } from '../chartModeStorage.js'
import { formatShortDateRange } from '../dates.js'

const { t, locale } = useI18n()
const lang = inject('lang')
// Initial window is left null: the period picker emits the restored (or default)
// selection on mount, which populates these and triggers the first fetch.
const start = ref(null)
const end = ref(null)
const periodLabel = ref('')
const currentPreset = ref('24h')
const sort = ref('most_frequent')
const species = ref([])
const loading = ref(false)
const viewMode = ref(window.innerWidth < 576 ? 'list' : 'grid')

const selectedSlugs = ref(new Set())
const chartSeries = ref([])
const chartGranularity = ref('day')

// How many species the chart shows. Unlike the period/sort filters, this scopes
// only the chart: it caps the selection and seeds it with the top-N species of
// the current ordering. Manual card toggles stay allowed within this budget.
const chartSpeciesCountOptions = [5, 10, 15, 20]
const chartSpeciesCount = ref(10)

const chartMode = ref(readChartMode())
const hourlySpecies = ref([])
const hourlyDays = ref(1)
// The hourly chart is fetched lazily: only when it is the visible chart. This
// flag marks its data as outdated after period/language/confidence changes so
// switching to it triggers a fetch.
const hourlyStale = ref(true)

// Navigation state
const navOffset = ref(0)
const navAnchor = ref(null)
const stepMs = ref(24 * 60 * 60 * 1000)
const floorDay = ref(false)
const liveStart = ref(null)
const liveEnd = ref(null)
const livePeriodLabel = ref('')

const canNavigate = computed(() => !!stepMs.value)
const isAtPresent = computed(() => navOffset.value === 0)

const navWindowLabel = computed(() => {
  if (!start.value) return ''
  const windowStart = new Date(start.value)
  const windowEnd = end.value ? new Date(end.value) : new Date()
  return formatShortDateRange(windowStart, windowEnd, locale.value)
})

function onPeriodChange({ preset, start: s, end: e, label, stepMs: sMs, floorDay: fd }) {
  navOffset.value = 0
  navAnchor.value = null
  currentPreset.value = preset
  stepMs.value = sMs ?? 0
  floorDay.value = fd ?? false
  start.value = s || null
  end.value = e || null
  periodLabel.value = label
  liveStart.value = s || null
  liveEnd.value = e || null
  livePeriodLabel.value = label
}

function updateNavWindow() {
  const anchor = navAnchor.value
  const stepMsValue = stepMs.value
  const windowEnd = new Date(anchor.getTime() - (navOffset.value - 1) * stepMsValue)
  const windowStart = new Date(anchor.getTime() - navOffset.value * stepMsValue)
  if (floorDay.value) {
    windowEnd.setHours(0, 0, 0, 0)
    windowStart.setHours(0, 0, 0, 0)
  }
  start.value = windowStart.toISOString()
  end.value = windowEnd.toISOString()
  periodLabel.value = formatShortDateRange(windowStart, windowEnd, locale.value)
}

function navigatePrev() {
  if (!canNavigate.value) return
  if (navOffset.value === 0) {
    navAnchor.value = new Date(start.value)
  }
  navOffset.value++
  updateNavWindow()
}

function navigateNext() {
  if (!canNavigate.value || navOffset.value === 0) return
  navOffset.value--
  if (navOffset.value === 0) {
    goToNow()
    return
  }
  updateNavWindow()
}

function goToNow() {
  navOffset.value = 0
  navAnchor.value = null
  start.value = liveStart.value
  end.value = liveEnd.value
  periodLabel.value = livePeriodLabel.value
}

async function fetchSpecies() {
  loading.value = true
  try {
    const fresh = await api.fetchSpeciesList({
      sort: sort.value,
      lang: lang.value,
      start: start.value,
      end: end.value,
    })
    species.value = fresh
    // Both charts follow this selection; the selectedSlugs watch refreshes them.
    selectedSlugs.value = new Set(fresh.slice(0, chartSpeciesCount.value).map((s) => s.slug))
  } finally {
    loading.value = false
  }
}

async function fetchChart() {
  if (!selectedSlugs.value.size) {
    chartSeries.value = []
    return
  }
  const data = await api.fetchDetectionsTimeline({
    speciesSlugs: [...selectedSlugs.value],
    lang: lang.value,
    start: start.value,
    end: end.value,
  })
  chartSeries.value = data.series
  chartGranularity.value = data.granularity
}

function setChartMode(mode) {
  chartMode.value = mode
  writeChartMode(mode)
  if (mode === 'hourly' && hourlyStale.value) fetchHourly()
}

async function fetchHourly() {
  if (!selectedSlugs.value.size) {
    hourlySpecies.value = []
    hourlyDays.value = 1
    hourlyStale.value = false
    return
  }
  const data = await api.fetchDetectionsByHourOfDay({
    speciesSlugs: [...selectedSlugs.value],
    lang: lang.value,
    start: start.value,
    end: end.value,
  })
  hourlySpecies.value = data.species
  hourlyDays.value = data.days
  hourlyStale.value = false
}

function toggleChart(slug) {
  const next = new Set(selectedSlugs.value)
  if (next.has(slug)) next.delete(slug)
  else if (next.size < chartSpeciesCount.value) next.add(slug)
  selectedSlugs.value = next
}

// Changing the chart's species count re-seeds the selection with the current
// top-N ordering, without refetching the list. The selectedSlugs watch below
// refreshes the charts.
watch(chartSpeciesCount, (count) => {
  selectedSlugs.value = new Set(species.value.slice(0, count).map((s) => s.slug))
})

// The period picker emits the restored (or default) window on mount, which
// flows through onPeriodChange and triggers the initial fetch via this watch,
// so no separate onMounted fetch is needed.
watch([start, end, sort, lang], fetchSpecies)

// Every input change (period, sort, language) reassigns
// selectedSlugs in fetchSpecies, and toggling a card reassigns it too, so a
// single watch keeps both charts in sync with the selection. The violin
// refetches eagerly; the hourly chart is lazy and only refetches when shown.
watch(selectedSlugs, () => {
  fetchChart()
  hourlyStale.value = true
  if (chartMode.value === 'hourly') fetchHourly()
})
</script>

<style scoped>
.nav-period-btn {
  padding: 1px 6px;
  line-height: 1.4;
}

.nav-period-label {
  min-width: 100px;
  text-align: center;
  font-size: 0.78rem;
}

.chart-empty-placeholder {
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.species-list-empty-placeholder {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.species-placeholder-row {
  height: 72px;
  border-radius: 8px;
  background: var(--warm-card);
  opacity: 0.5;
}
</style>
