<template>
  <div class="row g-2 hero-cards" :class="{ 'hero-cards--half': hasMap }">
    <template v-if="species.has_detections">
      <div class="col-12 col-lg-4">
        <div class="hero-stat hero-stat--detections">
          <i class="bi bi-bar-chart-line-fill hero-stat-icon"></i>
          <div class="hero-stat-body">
            <div class="hero-stat-value">{{ species.count_total?.toLocaleString() ?? 0 }}</div>
            <div class="hero-stat-label">{{ t('modal.tabDetections') }}</div>
            <div v-if="periodLabel" class="hero-stat-sub">{{ periodLabel }}</div>
          </div>
        </div>
      </div>
      <div class="col-12 col-lg-4">
        <div class="hero-stat hero-stat--lastseen">
          <i class="bi bi-calendar3 hero-stat-icon"></i>
          <div class="hero-stat-body">
            <div class="hero-stat-value">{{ lastSeenValue }}</div>
            <div class="hero-stat-label">{{ t('modal.lastSeen') }}</div>
            <div v-if="lastSeenTime" class="hero-stat-sub">{{ lastSeenTime }}</div>
          </div>
        </div>
      </div>
      <div class="col-12 col-lg-4">
        <div class="hero-stat hero-stat--recordings">
          <i class="bi bi-soundwave hero-stat-icon"></i>
          <div class="hero-stat-body">
            <div class="hero-stat-value">{{ species.recordings_total?.toLocaleString() ?? 0 }}</div>
            <div class="hero-stat-label">{{ t('modal.tabRecordings') }}</div>
            <div class="hero-stat-sub">{{ t('period.allTime') }}</div>
          </div>
        </div>
      </div>
    </template>

    <div v-for="card in highlightCards" :key="card.accent" class="col-12 col-lg-4">
      <div class="hero-stat" :class="`hero-stat--${card.accent}`">
        <i class="bi hero-stat-icon" :class="card.icon"></i>
        <div class="hero-stat-body">
          <div class="hero-stat-value" :class="{ 'hero-stat-value--text': card.isText }">
            {{ card.value }}
          </div>
          <div class="hero-stat-label">{{ card.label }}</div>
          <div v-if="card.sub" class="hero-stat-sub">{{ card.sub }}</div>
        </div>
      </div>
    </div>

    <!-- No map: seasonality joins the grid (there is no presence column to host it). -->
    <div v-if="!hasMap" :class="highlightCards.length ? 'col-12 col-lg-4' : 'col-12'">
      <SeasonalityChart :species-slug="speciesSlug" class="h-100" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import SeasonalityChart from '../charts/SeasonalityChart.vue'

const props = defineProps({
  species: { type: Object, required: true },
  speciesSlug: { type: String, required: true },
  highlights: { type: Array, default: null },
  periodLabel: { type: String, default: null },
})

const { t } = useI18n()

// When a map exists it hosts the seasonality chart in the presence column, so
// the cards reflow from 3-up to 2-up to sit beside it (see .hero-cards--half).
const hasMap = computed(() => Boolean(props.species.map_url))

// Last-seen day, kept short so it matches the other cards' value size:
// "Today" / "Yesterday" / "05/07/2026". The time (when recent) goes to the
// sub-line, mirroring the period/all-time sub on the neighbouring cards.
const lastSeenValue = computed(() => {
  if (!props.species.last_seen) return '—'
  const seen = dayjs(props.species.last_seen)
  if (seen.isSame(dayjs(), 'day')) return t('common.today')
  if (seen.isSame(dayjs().subtract(1, 'day'), 'day')) return t('common.yesterday')
  return seen.format('L')
})

const lastSeenTime = computed(() => {
  if (!props.species.last_seen) return null
  const seen = dayjs(props.species.last_seen)
  const isRecent = seen.isSame(dayjs(), 'day') || seen.isSame(dayjs().subtract(1, 'day'), 'day')
  return isRecent ? seen.format('LT') : null
})

// Behaviour highlights, rendered in the same anatomy as the KPI stats
// (accent-coloured icon + value, then a label, then an optional sub-line).
// Peak and streak promote their time/number to the big value slot; regularity
// has no number, so its phrase stays in the value slot as text (isText).
const highlightCards = computed(() =>
  (props.highlights ?? []).map((highlight) => {
    if (highlight.type === 'regularity') {
      return {
        accent: 'regularity',
        icon: 'bi-sun',
        value: t(`highlights.${highlight.tier}Visitor`),
        label: t(`highlights.${highlight.tier}VisitorDetail`),
        isText: true,
      }
    }
    if (highlight.type === 'peak') {
      return {
        accent: 'peak',
        icon: 'bi-graph-up-arrow',
        value: `${formatHour(highlight.startHour)}–${formatHour(highlight.endHour)}`,
        label: t('highlights.peakActivity'),
      }
    }
    return {
      accent: 'streak',
      icon: 'bi-calendar-check',
      value: highlight.days,
      label: t('highlights.streak'),
      sub: t('highlights.streakDaysUnit'),
    }
  }),
)

// Compact on-the-hour time for the peak value slot: drops the ":00" minutes so
// the range fits the big value size ("3 AM–6 AM" / "3–6"), locale-aware via LT.
function formatHour(hour) {
  return dayjs().hour(hour).minute(0).format('LT').replace(':00', '')
}
</script>

<style scoped>
/* Beside the presence column the cards reflow from 3-up to 2-up. */
@media (min-width: 992px) {
  .hero-cards--half > .col-lg-4 {
    width: 50%;
  }
}

.hero-stat {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  height: 100%;
  background: var(--sheet);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 0.7rem 0.85rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}
.hero-stat-icon {
  flex-shrink: 0;
  margin-top: 0.15rem;
  font-size: 1.55rem;
  line-height: 1;
  opacity: 0.9;
}
.hero-stat-body {
  min-width: 0;
}
.hero-stat-value,
.hero-stat-label,
.hero-stat-sub {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hero-stat-value {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.01em;
}
.hero-stat-label {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.72rem;
  color: var(--slate);
  margin-top: 2px;
}
.hero-stat-sub {
  font-size: 0.66rem;
  color: var(--slate);
  opacity: 0.7;
}
/* Every card is one of three accents, shared across the metric and highlight
   cards so the whole grid reads as one design family. */
.hero-stat--detections .hero-stat-value,
.hero-stat--detections .hero-stat-icon,
.hero-stat--streak .hero-stat-value,
.hero-stat--streak .hero-stat-icon {
  color: var(--jay-blue);
}
.hero-stat--lastseen .hero-stat-value,
.hero-stat--lastseen .hero-stat-icon,
.hero-stat--regularity .hero-stat-value,
.hero-stat--regularity .hero-stat-icon {
  color: var(--lichen);
}
.hero-stat--recordings .hero-stat-value,
.hero-stat--recordings .hero-stat-icon,
.hero-stat--peak .hero-stat-value,
.hero-stat--peak .hero-stat-icon {
  color: var(--ochre);
}
/* Regularity has no number: its value is a short phrase, so it drops to a
   text weight and may wrap to two lines instead of ellipsising. */
.hero-stat-value--text {
  font-size: 0.95rem;
  line-height: 1.2;
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
