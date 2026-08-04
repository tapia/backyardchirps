<template>
  <div v-if="timeline" class="seasonality-card">
    <div class="seasonality-head">
      <span class="seasonality-title">{{ t('chart.seasonalityTitle') }}</span>
      <i
        class="bi bi-info-circle seasonality-info"
        v-bs-tooltip.html.wide="legendTooltip"
        :aria-label="`${t('chart.lessProbable')} → ${t('chart.moreProbable')}`"
      ></i>
    </div>

    <div class="seasonality-band-wrap">
      <div class="seasonality-band" :style="{ background: bandGradient }"></div>
      <div class="seasonality-segments">
        <div
          v-for="segment in segments"
          :key="segment.date"
          class="seasonality-segment"
          v-bs-tooltip="segment.tooltip"
        ></div>
      </div>
      <div class="seasonality-marker" :style="{ left: markerLeft }">
        <span class="seasonality-marker-knob"></span>
      </div>
    </div>

    <div class="seasonality-months">
      <span v-for="quarter in quarters" :key="quarter" class="seasonality-month">{{
        quarter
      }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import * as api from '../../api/index.js'
import { CHART_COLORS } from '../../chartColors.js'

const props = defineProps({
  speciesSlug: { type: String, required: true },
})

const { t } = useI18n()

const timeline = ref(null)

const bandGradient = computed(() => {
  const entries = timeline.value
  if (!entries) return ''
  const stops = entries.map((entry, index) => {
    const position = ((index + 0.5) / entries.length) * 100
    return `${_colorForEntry(entry)} ${position.toFixed(2)}%`
  })
  return `linear-gradient(to right, ${stops.join(', ')})`
})

// Tooltip for the info icon: the same "less → more probable" colour legend
// that used to sit under the band, rendered as a small gradient bar. Built as
// trusted markup (gradient comes from CHART_COLORS) for v-bs-tooltip.html.
const legendTooltip = computed(() => {
  const gradient = `linear-gradient(to right, ${CHART_COLORS.seasonalityGradient.join(', ')})`
  return (
    '<span style="display:inline-flex;flex-direction:column;align-items:center;gap:4px">' +
    '<span style="display:inline-flex;align-items:center;gap:6px;white-space:nowrap">' +
    `<span>${t('chart.lessProbable')}</span>` +
    `<span style="display:inline-block;width:64px;height:8px;border-radius:4px;background:${gradient}"></span>` +
    `<span>${t('chart.moreProbable')}</span>` +
    '</span>' +
    `<span style="opacity:0.75">${t('chart.seasonalitySource')}</span>` +
    '</span>'
  )
})

const segments = computed(() =>
  (timeline.value ?? []).map((entry) => ({
    date: entry.date,
    tooltip:
      entry.probability == null
        ? `${dayjs(entry.date).format('MMM D')} · ${t('chart.seasonalityNoData')}`
        : `${dayjs(entry.date).format('MMM D')} · ${t('chart.seasonalityChance', {
            pct: Math.round(entry.probability * 100),
          })}`,
  })),
)

const markerLeft = computed(() => {
  const entries = timeline.value
  if (!entries) return '0%'
  return `${((_currentWeekIndex(entries) + 0.5) / entries.length) * 100}%`
})

// Quarterly axis labels (Jan / Apr / Jul / Oct), localised via the app-wide
// dayjs locale, aligned to the start of each quarter of the band.
const quarters = computed(() => [0, 3, 6, 9].map((month) => dayjs().month(month).format('MMM')))

async function load() {
  timeline.value = await api.fetchSpeciesSeasonality(props.speciesSlug)
}

// Index of the weekly band closest to today (year-agnostic), marking where
// "now" falls in the yearly cycle.
function _currentWeekIndex(entries) {
  const today = dayjs()
  let bestIndex = 0
  let smallestGap = Infinity
  entries.forEach((entry, index) => {
    const gap = Math.abs(dayjs(entry.date).year(today.year()).diff(today, 'day'))
    if (gap < smallestGap) {
      smallestGap = gap
      bestIndex = index
    }
  })
  return bestIndex
}

// The colour ramp maps the absolute occurrence probability (0–100%), so a
// species that never exceeds 1% stays at the low end of the ramp rather than
// being stretched to its own peak.
function _colorForEntry(entry) {
  const ratio = entry.probability == null ? 0 : entry.probability
  return _colorForRatio(ratio)
}

// Linear interpolation across the seasonality colour ramp for a 0–1 ratio.
function _colorForRatio(ratio) {
  const stops = CHART_COLORS.seasonalityGradient
  const scaled = Math.max(0, Math.min(1, ratio)) * (stops.length - 1)
  const lowerIndex = Math.floor(scaled)
  const upperIndex = Math.min(lowerIndex + 1, stops.length - 1)
  return _mixColors(stops[lowerIndex], stops[upperIndex], scaled - lowerIndex)
}

function _mixColors(lowerHex, upperHex, fraction) {
  const lower = _hexToRgb(lowerHex)
  const upper = _hexToRgb(upperHex)
  const channel = (component) =>
    Math.round(lower[component] + (upper[component] - lower[component]) * fraction)
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`
}

function _hexToRgb(hex) {
  const value = parseInt(hex.slice(1), 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}

watch(() => props.speciesSlug, load)
onMounted(load)
</script>

<style scoped>
.seasonality-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: var(--sheet);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 0.45rem 0.85rem 0.4rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

/* ── Header: title + info tooltip ────────────────────────────────── */
.seasonality-head {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.3rem;
}
.seasonality-title {
  min-width: 0;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--graphite);
  line-height: 1.2;
}
.seasonality-info {
  flex-shrink: 0;
  margin-left: auto;
  font-size: 0.8rem;
  color: var(--slate);
  opacity: 0.6;
  cursor: help;
}

/* ── Gradient band ───────────────────────────────────────────────── */
.seasonality-band-wrap {
  position: relative;
  height: 28px;
}
.seasonality-band {
  position: absolute;
  inset: 0;
  border-radius: 5px;
}
.seasonality-segments {
  position: absolute;
  inset: 0;
  display: flex;
}
.seasonality-segment {
  flex: 1 1 0;
}

/* ── "This week" marker ──────────────────────────────────────────── */
.seasonality-marker {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 0;
  border-left: 2px solid var(--seasonality-marker);
  transform: translateX(-1px);
  pointer-events: none;
}
.seasonality-marker-knob {
  position: absolute;
  top: 50%;
  left: 0;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: var(--seasonality-marker);
  border: 2.5px solid #fff;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.15);
  transform: translate(-50%, -50%);
}

/* ── Quarterly axis ──────────────────────────────────────────────── */
.seasonality-months {
  display: flex;
  margin-top: 3px;
}
.seasonality-month {
  position: relative;
  flex: 1 1 0;
  padding-left: 4px;
  font-size: 0.68rem;
  color: var(--warm-muted);
}
.seasonality-month::before {
  content: '';
  position: absolute;
  top: -4px;
  left: 0;
  width: 1px;
  height: 4px;
  background: var(--limestone);
}
</style>
