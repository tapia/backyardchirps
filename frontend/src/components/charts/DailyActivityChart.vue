<template>
  <div
    class="mb-4 chart-card daily-activity-card"
    :style="{
      '--plot-inset-left': GRID_LEFT + 'px',
      '--plot-inset-right': GRID_RIGHT + 'px',
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
    <VChart class="daily-activity-plot" :option="option" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { use, format } from 'echarts/core'
import { BarChart, ScatterChart } from 'echarts/charts'
import { GridComponent, MarkAreaComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import { CHART_COLORS } from '../../chartColors.js'

use([BarChart, CanvasRenderer, GridComponent, MarkAreaComponent, ScatterChart, TooltipComponent])

const { t } = useI18n()

const props = defineProps({
  // [{ hour, count, species_counts: { scientific name: count }, top_species: [...] }]
  hours: { type: Array, required: true },
  astro: { type: Object, default: null },
  // Bars containing this species stay highlighted while the rest dim.
  hoveredSpeciesName: { type: String, default: null },
})

const HOUR_MS = 3600000

// Canvas text cannot read CSS custom properties, so the font stack is written out.
const AXIS_FONT = "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif"

// Plot edges inside the chart. The HTML header above uses the same insets, so its
// legend lines up with the first bar and its navigation with the last.
const GRID_LEFT = 36
const GRID_RIGHT = 8
const GRID_TOP = 18
const GRID_BOTTOM = 34
// Bars fill this share of their hour, as Chart.js drew them.
const BAR_GAP = '28%'
const BAR_CORNER_RADIUS = 3
const Y_AXIS_HEADROOM = 1.15
const Y_AXIS_STEPS = 10

// Which zone starts after each astro event, and the bootstrap-icons glyph inside it.
const ZONE_AFTER = { sunrise: 'day', sunset: 'night' }
const ZONE_STYLES = {
  night: {
    color: CHART_COLORS.dayNight.night,
    icon: String.fromCodePoint(0xf494),
    iconColor: CHART_COLORS.dayNight.moonIcon,
  },
  day: {
    color: CHART_COLORS.dayNight.day,
    icon: String.fromCodePoint(0xf5a1),
    iconColor: CHART_COLORS.dayNight.sunIcon,
  },
}
const ZONE_ICON_SIZE = 24
const ZONE_ICON_TOP = 12
// A zone shorter than this is left without an icon.
const ZONE_ICON_MIN_HOURS = 1.5

// Gap between the tooltip card and the top of the bar it describes.
const TOOLTIP_OFFSET = 12

const sunriseLabel = computed(() => lastEventTime('sunrise'))
const sunsetLabel = computed(() => lastEventTime('sunset'))

const option = computed(() => {
  const segments = props.hours.map(barSegments)
  const speciesHovered = Boolean(props.hoveredSpeciesName)
  const restColor = speciesHovered ? CHART_COLORS.hourlyBarDimmed : CHART_COLORS.hourlyBar
  const axisText = { color: CHART_COLORS.axis, fontSize: 13, fontFamily: AXIS_FONT }

  return {
    // Updates apply at once: animating the stacked parts separately shows seams in the bars.
    animationDurationUpdate: 0,
    grid: { left: GRID_LEFT, right: GRID_RIGHT, top: GRID_TOP, bottom: GRID_BOTTOM },
    xAxis: [
      {
        type: 'category',
        data: props.hours.map((hour) => dayjs(hour.hour).format('hA')),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: axisText,
      },
      // Hours as a continuous scale, for day/night edges that fall inside an hour.
      { type: 'value', min: 0, max: props.hours.length, show: false },
    ],
    yAxis: {
      type: 'value',
      // Room above the tallest bar; the top of the axis gets no label and no line.
      max: ({ max }) => Math.max(max, 1) * Y_AXIS_HEADROOM,
      splitNumber: Y_AXIS_STEPS,
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...axisText, showMaxLabel: false },
      splitLine: { showMaxLine: false, lineStyle: { color: CHART_COLORS.grid } },
    },
    tooltip: {
      trigger: 'item',
      className: 'chart-tooltip',
      appendTo: 'body',
      backgroundColor: CHART_COLORS.tooltip.background,
      borderColor: CHART_COLORS.tooltip.border,
      borderWidth: 1,
      padding: [8, 10],
      extraCssText: 'border-radius: 2px; box-shadow: none;',
      position: tooltipPosition,
      formatter: tooltipHtml,
    },
    /*
     * Each bar is a stack of three parts. Normally the whole count sits in the
     * first. While a species is hovered, the middle part is that species' share,
     * drawn in the highlight colour, and the parts around it are dimmed.
     */
    series: [
      stackPart(segments, 0, restColor),
      stackPart(segments, 1, CHART_COLORS.hourlyBarHighlight),
      stackPart(segments, 2, restColor),
      {
        type: 'scatter',
        xAxisIndex: 1,
        data: [],
        silent: true,
        z: 1,
        markArea: {
          silent: true,
          label: {
            position: 'insideTop',
            distance: ZONE_ICON_TOP,
            fontFamily: 'bootstrap-icons',
            fontSize: ZONE_ICON_SIZE,
          },
          data: dayNightZones().map((zone) => [
            {
              name: ZONE_STYLES[zone.type].icon,
              xAxis: zone.start,
              itemStyle: { color: ZONE_STYLES[zone.type].color },
              label: {
                show: zone.end - zone.start >= ZONE_ICON_MIN_HOURS,
                color: ZONE_STYLES[zone.type].iconColor,
              },
            },
            { xAxis: zone.end },
          ]),
        },
      },
    ],
  }
})

function lastEventTime(key) {
  const events = (props.astro?.events || []).filter((event) => event.key === key)
  if (!events.length) return null
  return dayjs(events[events.length - 1].time).format('LT')
}

function stackPart(segments, part, color) {
  return {
    type: 'bar',
    stack: 'hour',
    barCategoryGap: BAR_GAP,
    itemStyle: { color },
    data: segments.map((parts) => ({
      value: parts[part],
      // Only the part on top of the stack gets the rounded corners.
      itemStyle: {
        borderRadius: part === topPart(parts) ? [BAR_CORNER_RADIUS, BAR_CORNER_RADIUS, 0, 0] : 0,
      },
    })),
  }
}

function topPart(parts) {
  return parts.findLastIndex((value) => value > 0)
}

/*
 * The three parts of one hour's bar: [below, hovered species, above]. Within a
 * bar the species are stacked from the most detected down, name as tiebreak, so
 * each species keeps its own band whichever one is hovered.
 */
function barSegments(hour) {
  const total = hour.count || 0
  const speciesCounts = hour.species_counts || {}
  const hoveredCount = speciesCounts[props.hoveredSpeciesName] || 0
  if (!hoveredCount) return [total, 0, 0]

  const orderedNames = Object.keys(speciesCounts).sort(
    (first, second) => speciesCounts[second] - speciesCounts[first] || first.localeCompare(second),
  )
  const below = orderedNames
    .slice(0, orderedNames.indexOf(props.hoveredSpeciesName))
    .reduce((sum, name) => sum + speciesCounts[name], 0)
  return [below, hoveredCount, Math.max(total - below - hoveredCount, 0)]
}

/*
 * Day and night stretches across the chart, as positions on the continuous hour
 * scale: 0 is the start of the first bar's hour, hours.length the end of the last.
 */
function dayNightZones() {
  const events = props.astro?.events
  if (!events || !props.hours.length) return []
  const startMs = new Date(props.hours[0].hour).getTime()
  const hourCount = props.hours.length
  const boundaries = events
    .filter((event) => event.key in ZONE_AFTER)
    .map((event) => ({
      position: (new Date(event.time).getTime() - startMs) / HOUR_MS,
      nextType: ZONE_AFTER[event.key],
    }))
    .sort((first, second) => first.position - second.position)

  let type = 'night'
  for (const boundary of boundaries) {
    if (boundary.position <= 0) type = boundary.nextType
  }
  const zones = []
  let start = 0
  for (const boundary of boundaries) {
    if (boundary.position <= 0) continue
    if (boundary.position >= hourCount) break
    zones.push({ type, start, end: boundary.position })
    type = boundary.nextType
    start = boundary.position
  }
  zones.push({ type, start, end: hourCount })
  return zones
}

function tooltipHtml(params) {
  const hour = props.hours[params.dataIndex]
  if (!hour) return ''
  const topSpecies = hour.top_species || []
  const header =
    `<div class="chart-tooltip__header">` +
    `<span class="chart-tooltip__time" style="color: ${CHART_COLORS.tooltip.title}">` +
    `${format.encodeHTML(dayjs(hour.hour).format('LT'))}</span>` +
    `<span class="chart-tooltip__header-count" style="color: ${CHART_COLORS.tooltip.body}">` +
    `${format.encodeHTML(`${hour.count} ${t('chart.detections')}`)}</span></div>`

  if (!topSpecies.length) {
    return (
      header +
      `<div class="chart-tooltip__empty" style="color: ${CHART_COLORS.tooltip.body}">` +
      `${format.encodeHTML(t('chart.noDetections'))}</div>`
    )
  }

  const rows = topSpecies.map((species) =>
    tooltipRow(
      `<img class="chart-tooltip__img" src="${format.encodeHTML(species.image_url ?? '')}" ` +
        `alt="" onerror="this.style.display='none'">`,
      species.common_name,
      species.scientific_name,
      species.count,
    ),
  )
  const othersCount = hour.count - topSpecies.reduce((sum, species) => sum + species.count, 0)
  if (othersCount > 0) {
    rows.push(
      tooltipRow(
        '<div class="chart-tooltip__placeholder"></div>',
        t('chart.othersDetections'),
        null,
        othersCount,
      ),
    )
  }
  return header + rows.join('')
}

function tooltipRow(pictureHtml, name, scientificName, count) {
  const scientific = scientificName
    ? `<div class="chart-tooltip__sci-name" style="color: ${CHART_COLORS.axis}">` +
      `${format.encodeHTML(scientificName)}</div>`
    : ''
  return (
    `<div class="chart-tooltip__row">${pictureHtml}<div class="chart-tooltip__names">` +
    `<div class="chart-tooltip__common-name" style="color: ${CHART_COLORS.tooltip.body}">` +
    `${format.encodeHTML(name)}</div>${scientific}</div>` +
    `<span class="chart-tooltip__count" style="color: ${CHART_COLORS.tooltip.title}">` +
    `${count}</span></div>`
  )
}

// Centred on the bar, above it when the card fits inside the chart, below its top otherwise.
function tooltipPosition(point, params, element, rect, size) {
  const [cardWidth, cardHeight] = size.contentSize
  const above = rect.y - cardHeight - TOOLTIP_OFFSET
  return [rect.x + rect.width / 2 - cardWidth / 2, above >= 0 ? above : rect.y + TOOLTIP_OFFSET]
}
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
  height: 250px;
}

/* Tooltip card built by tooltipHtml(); ECharts places it on <body>. */
.chart-tooltip {
  min-width: 210px;
  max-width: 260px;
  font-family: var(--font-sans);
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
