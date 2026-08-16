<template>
  <div
    class="mb-4 chart-card daily-activity-card"
    :style="{
      '--plot-inset-left': plotInsetLeft + 'px',
      '--plot-inset-right': plotInsetRight + 'px',
    }"
  >
    <div class="daily-activity-header">
      <div class="astro-legend">
        <span v-if="sunriseLabel" class="astro-legend__item">
          <i class="bi bi-sun-fill astro-legend__icon astro-legend__icon--sun"></i>
          <span class="astro-legend__text">
            <span class="astro-legend__label">{{ t('chart.sunrise') }}</span> {{ sunriseLabel }}
          </span>
        </span>
        <span v-if="sunriseLabel && sunsetLabel" class="astro-legend__divider"></span>
        <span v-if="sunsetLabel" class="astro-legend__item">
          <i class="bi bi-moon-fill astro-legend__icon astro-legend__icon--moon"></i>
          <span class="astro-legend__text">
            <span class="astro-legend__label">{{ t('chart.sunset') }}</span> {{ sunsetLabel }}
          </span>
        </span>
      </div>
      <div class="daily-activity-nav">
        <slot name="nav" />
      </div>
    </div>
    <div class="daily-activity-plot">
      <canvas ref="canvas" class="chart-canvas"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js'
import dayjs from 'dayjs'
import { CHART_COLORS } from '../../chartColors.js'
import { createDayNightPlugins } from './dayNightBackground.js'
import { createHourlyBreakdownTooltip } from './hourlyBreakdownTooltip.js'
import { createSpeciesProportionPlugin } from './speciesProportionOverlay.js'

const { t } = useI18n()

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

const props = defineProps({
  hours: { type: Array, required: true },
  astro: { type: Object, default: null },
  // Bars containing this species stay highlighted while the rest dim.
  hoveredSpeciesName: { type: String, default: null },
})

const canvas = ref(null)
let chart = null
let breakdownTooltip = null

// Horizontal insets (px) of the plotting rectangle within the canvas, so the
// HTML header can align its legend with the left edge of the bars (right of the
// Y-axis labels) and its nav with the right edge of the bars.
const plotInsetLeft = ref(0)
const plotInsetRight = ref(0)

const sunriseLabel = computed(() => lastEventTime('sunrise'))
const sunsetLabel = computed(() => lastEventTime('sunset'))

function lastEventTime(key) {
  const events = (props.astro?.events || []).filter((event) => event.key === key)
  if (!events.length) return null
  return dayjs(events[events.length - 1].time).format('LT')
}

function init() {
  if (!canvas.value) return
  breakdownTooltip = createHourlyBreakdownTooltip({ getHours: () => props.hours, translate: t })
  chart = new Chart(canvas.value, {
    type: 'bar',
    plugins: [
      ...createDayNightPlugins({
        getHours: () => props.hours,
        getAstro: () => props.astro,
      }),
      createSpeciesProportionPlugin({
        getHours: () => props.hours,
        getHoveredSpeciesName: () => props.hoveredSpeciesName,
      }),
      {
        id: 'plot-inset',
        afterLayout(chartInstance) {
          plotInsetLeft.value = Math.round(chartInstance.chartArea.left)
          plotInsetRight.value = Math.round(chartInstance.width - chartInstance.chartArea.right)
        },
      },
    ],
    data: {
      labels: props.hours.map((h) => dayjs(h.hour).format('hA')),
      datasets: [
        {
          data: props.hours.map((h) => h.count || 0),
          backgroundColor: barBackground,
          borderRadius: 3,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      layout: {
        padding: { top: 10, bottom: 8, left: 8, right: 8 },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: false,
          external: breakdownTooltip.handler,
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxTicksLimit: 25, font: { size: 13 }, color: CHART_COLORS.axis },
          border: { display: false },
        },
        y: {
          beginAtZero: true,
          grace: '15%',
          ticks: { precision: 0, font: { size: 13 }, color: CHART_COLORS.axis },
          grid: { color: CHART_COLORS.grid },
          border: { display: false },
        },
      },
    },
  })
}

function barBackground() {
  // Each bar is a flat forest fill.
  // While a species is hovered every bar is drawn dimmed instead; the species'
  // share of each bar is painted back in the highlight colour by
  // createSpeciesProportionPlugin, so a bar reads as split into the part that
  // belongs to the species and the rest.
  if (props.hoveredSpeciesName) return CHART_COLORS.hourlyBarDimmed
  return CHART_COLORS.hourlyBar
}

function updateData() {
  if (!chart) return
  chart.data.labels = props.hours.map((h) => dayjs(h.hour).format('hA'))
  chart.data.datasets[0].data = props.hours.map((h) => h.count || 0)
  chart.update()
}

onMounted(init)
onUnmounted(() => {
  chart?.destroy()
  breakdownTooltip?.destroy()
})
watch(() => props.hours, updateData)
watch(
  () => props.hoveredSpeciesName,
  () => chart?.update(),
)
watch(
  () => props.astro,
  () => chart?.update(),
)
</script>

<style>
.daily-activity-card {
  position: relative;
  overflow: hidden;
  padding: 14px 16px 10px;
}
.daily-activity-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
  min-height: 30px;
  /* Align the header with the plotting rectangle, not the Y-axis labels. */
  padding-left: var(--plot-inset-left, 0px);
  padding-right: var(--plot-inset-right, 0px);
}
.astro-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-sans);
  font-size: 0.85rem;
}
.astro-legend__item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
}
.astro-legend__icon {
  font-size: 1.05rem;
  line-height: 1;
}
.astro-legend__icon--sun {
  color: var(--sun-gold);
}
.astro-legend__icon--moon {
  color: var(--night-violet);
}
.astro-legend__text {
  color: var(--graphite);
  font-weight: 600;
}
.astro-legend__label {
  color: var(--warm-muted);
  font-weight: 500;
}
.astro-legend__divider {
  width: 1px;
  height: 18px;
  background: var(--limestone);
}
.daily-activity-nav {
  margin-left: auto;
}

/* On phones, stack the header: date selector on top, astro legend below it. */
@media (max-width: 575.98px) {
  .daily-activity-header {
    flex-direction: column-reverse;
    align-items: stretch;
    gap: 12px;
    margin-bottom: 2px;
    padding-left: 0;
    padding-right: 6px;
  }
  .daily-activity-nav {
    display: flex;
    justify-content: flex-end;
  }
  .astro-legend {
    justify-content: flex-end;
  }
}

.daily-activity-plot {
  position: relative;
  min-height: 250px;
}
.chart-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* Tooltip card built by hourlyBreakdownTooltip.js (appended to <body>). */
.chart-tooltip {
  position: fixed;
  pointer-events: none;
  z-index: 9999;
  border: 1px solid;
  border-radius: 2px;
  padding: 8px 10px;
  min-width: 210px;
  max-width: 260px;
  font-family: var(--font-sans);
  opacity: 0;
  transition: opacity 0.12s ease;
}
.chart-tooltip--visible {
  opacity: 1;
}
.chart-tooltip__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}
.chart-tooltip__time {
  font-size: 13px;
  font-weight: 600;
}
.chart-tooltip__header-count {
  font-size: 12px;
}
.chart-tooltip__empty {
  font-size: 12px;
}
.chart-tooltip__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.chart-tooltip__img {
  width: 56px;
  height: 56px;
  border-radius: 1px;
  object-fit: cover;
  flex-shrink: 0;
}
.chart-tooltip__names {
  flex: 1;
  min-width: 0;
}
.chart-tooltip__common-name {
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chart-tooltip__sci-name {
  font-family: var(--font-serif);
  font-size: 13px;
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chart-tooltip__count {
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.chart-tooltip__placeholder {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
}
</style>
