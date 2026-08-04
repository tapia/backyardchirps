<template>
  <div class="container pb-5">
    <div v-if="hours.length" class="chart-wrapper">
      <DailyActivityChart :hours="hours" :astro="astro" :hovered-species-name="hoveredSpeciesName">
        <template #nav>
          <div class="btn-group btn-group-sm">
            <button
              type="button"
              class="btn btn-outline-secondary nav-period-btn"
              @click="navigatePrev"
            >
              <i class="bi bi-chevron-left"></i>
            </button>
            <span class="btn btn-outline-secondary pe-none nav-period-label">
              <template v-if="isLive">{{ t('page.recent.live') }}</template>
              <template v-else>{{ navWindowLabel }}</template>
            </span>
            <button
              type="button"
              class="btn btn-outline-secondary nav-period-btn"
              :disabled="isLive"
              @click="navigateNext"
            >
              <i class="bi bi-chevron-right"></i>
            </button>
            <button
              type="button"
              class="btn btn-outline-secondary nav-period-btn"
              :disabled="isLive"
              v-bs-tooltip="t('period.now')"
              @click="goToNow"
            >
              <i class="bi bi-chevron-double-right"></i>
            </button>
          </div>
        </template>
      </DailyActivityChart>
    </div>

    <div v-if="loading" class="text-center py-5 text-warm-muted">
      <div class="spinner-border spinner-border-sm me-2"></div>
      {{ t('common.loading') }}
    </div>

    <template v-else-if="species.length > 0">
      <div class="mb-2">
        <span class="small text-warm-muted">{{
          isLive
            ? t('page.recent.subtitle', { n: species.length })
            : t('page.recent.subtitlePeriod', { n: species.length, period: navWindowLabel })
        }}</span>
      </div>

      <!-- Mobile: table -->
      <div class="d-sm-none species-table-card">
        <table class="species-table w-100">
          <thead>
            <tr>
              <th colspan="2" class="species-table__th-name"></th>
              <th class="species-table__th-count">
                <span class="th-line">{{ t('common.detsShort') }}</span>
                <span class="th-line">{{ navPeriodLabel }}</span>
              </th>
              <th v-if="isLive" class="species-table__th-time">{{ t('common.lastSeenShort') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in species"
              :key="s.slug"
              class="species-table__row"
              :class="{ flash: flashSlugs.has(s.slug) }"
              @mouseenter="hoveredSpeciesName = s.scientific_name"
              @mouseleave="hoveredSpeciesName = null"
            >
              <td class="species-table__img-cell">
                <RouterLink
                  :to="speciesRoute(s.slug)"
                  class="stretched-link"
                  :aria-label="s.common_name"
                />
                <img
                  :src="s.image_url"
                  :alt="s.common_name"
                  class="species-table__img rounded"
                  @error="$event.target.style.display = 'none'"
                />
              </td>
              <td class="species-table__name">
                <div class="tbl-bird-name">{{ s.common_name }}</div>
                <div class="tbl-sci-name">{{ s.scientific_name }}</div>
              </td>
              <td class="species-table__count">{{ s.count_in_period?.toLocaleString() }}</td>
              <td v-if="isLive" class="species-table__time">
                {{ shortRelativeTime(s.last_seen) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Desktop: card grid -->
      <div class="d-none d-sm-grid feed-grid">
        <DetectionsFeedItem
          v-for="s in species"
          :key="s.slug"
          :species="s"
          :flash="flashSlugs.has(s.slug)"
          :period-label="cardPeriodLabel"
          :show-last-seen="isLive"
          card
          :to="speciesRoute(s.slug)"
          @mouseenter="hoveredSpeciesName = s.scientific_name"
          @mouseleave="hoveredSpeciesName = null"
        />
      </div>
    </template>

    <div v-else class="text-warm-muted text-center py-5">{{ t('page.recent.empty') }}</div>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '../api/index.js'
import { shortRelativeTime } from '../dates.js'
import { speciesRoute } from '../links.js'
import DetectionsFeedItem from '../components/feed/DetectionsFeedItem.vue'
import DailyActivityChart from '../components/charts/DailyActivityChart.vue'
import { useConfidenceFilter } from '../composables/useConfidenceFilter.js'

const { t, locale } = useI18n()
const lang = inject('lang')
const { confidenceLevel } = useConfidenceFilter()
const species = ref([])
const hours = ref([])
const astro = ref(null)
const loading = ref(false)
const flashSlugs = ref(new Set())
const navOffset = ref(0)
const hoveredSpeciesName = ref(null)

const STEP_MS = 24 * 60 * 60 * 1000

const isLive = computed(() => navOffset.value === 0)

const navWindowLabel = computed(() => {
  const now = Date.now()
  const windowStart = new Date(now - (navOffset.value + 1) * STEP_MS)
  const windowEnd = isLive.value ? new Date(now) : new Date(now - navOffset.value * STEP_MS)
  const fmt = (date) => date.toLocaleDateString(locale.value, { month: 'short', day: 'numeric' })
  return `${fmt(windowStart)} – ${fmt(windowEnd)}`
})

const navPeriodLabel = computed(() => (isLive.value ? '24h' : navWindowLabel.value))
const cardPeriodLabel = computed(() =>
  isLive.value ? t('common.detectionsInPeriod', { period: '24h' }) : navWindowLabel.value,
)

let prevSnapshot = null
let flashTimer = null
let timer

function currentWindowParams() {
  const now = Date.now()
  const start = new Date(now - (navOffset.value + 1) * STEP_MS)
  const end = isLive.value ? null : new Date(now - navOffset.value * STEP_MS)
  return { start, end }
}

async function refresh(isInitial = false) {
  if (isInitial) loading.value = true
  try {
    const { start, end } = currentWindowParams()
    const [fresh, hourly] = await Promise.all([
      api.fetchSpeciesList({
        sort: 'most_recent',
        lang: lang.value,
        start: start.toISOString(),
        end: end?.toISOString(),
        minConfidence: confidenceLevel.value,
      }),
      api.fetchDetectionsPerSpeciesPerHour({
        lang: lang.value,
        minConfidence: confidenceLevel.value,
        daysBack: navOffset.value,
      }),
    ])

    if (isLive.value && prevSnapshot) {
      const changed = new Set(
        fresh.filter((s) => prevSnapshot.get(s.slug) !== s.last_seen).map((s) => s.slug),
      )
      if (changed.size) {
        flashSlugs.value = changed
        clearTimeout(flashTimer)
        flashTimer = setTimeout(() => {
          flashSlugs.value = new Set()
        }, 1200)
      }
    }

    prevSnapshot = isLive.value ? new Map(fresh.map((s) => [s.slug, s.last_seen])) : null
    species.value = fresh
    hours.value = hourly.hours
    if (hourly.astro) astro.value = hourly.astro
  } finally {
    if (isInitial) loading.value = false
  }
}

function navigatePrev() {
  navOffset.value++
}

function navigateNext() {
  if (isLive.value) return
  navOffset.value--
}

function goToNow() {
  navOffset.value = 0
}

function startRefreshTimer() {
  clearInterval(timer)
  if (isLive.value) {
    timer = setInterval(() => refresh(), 3000)
  }
}

watch(navOffset, () => {
  prevSnapshot = null
  flashSlugs.value = new Set()
  startRefreshTimer()
  refresh(false)
})

onMounted(() => {
  refresh(true)
  startRefreshTimer()
})
onUnmounted(() => clearInterval(timer))
watch([confidenceLevel, lang], () => refresh())
</script>

<style scoped>
.nav-period-btn {
  padding: 1px 6px;
  line-height: 1.4;
}

.nav-period-label {
  min-width: 80px;
  text-align: center;
  font-size: 0.78rem;
}

.feed-grid {
  grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
  gap: 1.25rem;
}

.species-table-card {
  background: var(--sheet);
  border: 1px solid var(--limestone);
  border-radius: 2px;
  overflow: hidden;
}

.species-table {
  border-collapse: collapse;
}

.species-table thead th {
  padding: 8px 10px;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.58rem;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--slate);
  font-weight: 600;
  white-space: nowrap;
  background: var(--paper);
  border-bottom: 1px solid var(--limestone);
}
.species-table__th-name {
  padding-left: 12px;
}
.species-table__th-count {
  text-align: right;
}
.species-table__th-time {
  text-align: right;
  padding-right: 12px;
}
.th-line {
  display: block;
  line-height: 1.3;
}

.species-table__row {
  position: relative;
  cursor: pointer;
  border-bottom: 1px solid var(--limestone);
  transition: background 0.1s;
}
.species-table__row:hover {
  background: var(--lichen-pale);
}

.species-table__img-cell {
  padding: 6px 8px 6px 12px;
  width: 74px;
}
.species-table__img {
  width: 62px;
  height: 62px;
  object-fit: cover;
  display: block;
  border-radius: 1px;
}

.species-table__name {
  padding: 10px 12px 10px 0;
}
.tbl-bird-name {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 0.93rem;
  font-weight: 500;
  color: var(--graphite);
}
.tbl-sci-name {
  font-family: 'Newsreader', Georgia, serif;
  font-style: italic;
  font-size: 0.73rem;
  color: var(--slate);
  margin-top: 2px;
}

.species-table__count {
  text-align: right;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--graphite);
  white-space: nowrap;
  padding: 10px 12px;
  vertical-align: middle;
}
.species-table__time {
  text-align: right;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.82rem;
  color: var(--slate);
  white-space: nowrap;
  padding: 10px 12px;
  vertical-align: middle;
}

@keyframes flash-table-row {
  0% {
    background-color: rgba(var(--lichen-rgb), 0.14);
  }
  100% {
    background-color: transparent;
  }
}
.species-table__row.flash {
  animation: flash-table-row 1.2s ease-out;
}
</style>
