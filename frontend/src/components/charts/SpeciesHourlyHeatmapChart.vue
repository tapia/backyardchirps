<template>
  <div class="stat-card-warm p-3">
    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">
      <div class="chart-label">{{ t('chart.speciesByHour') }}</div>
      <div class="btn-group btn-group-sm">
        <button
          type="button"
          class="btn"
          :class="metric === 'total' ? 'btn-primary' : 'btn-outline-primary'"
          @click="metric = 'total'"
        >
          {{ t('chart.metricTotal') }}
        </button>
        <button
          type="button"
          class="btn"
          :class="metric === 'daily' ? 'btn-primary' : 'btn-outline-primary'"
          @click="metric = 'daily'"
        >
          {{ t('chart.metricDailyAverage') }}
        </button>
      </div>
    </div>
    <VChart :option="option" :style="{ height: chartHeight + 'px' }" autoresize />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { use, format } from 'echarts/core'
import { BarChart, HeatmapChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  GridComponent,
  TooltipComponent,
  VisualMapPiecewiseComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { CHART_COLORS } from '../../chartColors.js'
import { formatHourOfDay } from './chartLabels.js'
import { HEADER_FONT, TOOLTIP_STYLE, axisText } from './chartStyle.js'
import {
  HEATMAP_TOP,
  LABEL_GAP,
  activityLegend,
  activityLevel,
  heatmapGrid,
  heatmapSeries,
  narrowBarsWidth,
  totalsGrid,
  totalsSeries,
  totalsXAxis,
  totalsYAxis,
} from './heatmapHeader.js'

use([
  AxisPointerComponent,
  BarChart,
  CanvasRenderer,
  GridComponent,
  HeatmapChart,
  TooltipComponent,
  VisualMapPiecewiseComponent,
])

const { t } = useI18n()

const props = defineProps({
  // [{ scientific_name, common_name, image_url, total, hours: [24 ints] }]
  species: { type: Array, required: true },
  // Days the selected period spans, for the daily-average metric.
  days: { type: Number, required: true },
})

const metric = ref('total')

const HOURS = Array.from({ length: 24 }, (unused, hour) => hour)

const AXIS_TEXT = axisText(12)

const HEATMAP_BOTTOM = 28
// Species names wrap to this width.
const LABEL_WIDTH = 100
const PLOT_LEFT = LABEL_WIDTH + 2 * LABEL_GAP
// Below this chart width the bars are too narrow to carry their values (only the
// hovered one shows it), the hours are labelled every six, and names wrap sooner.
const NARROW_WIDTH = narrowBarsWidth(PLOT_LEFT, HOURS.length)
const NARROW_LABEL_WIDTH = 76
const NARROW_PLOT_LEFT = NARROW_LABEL_WIDTH + 2 * LABEL_GAP

// Above this many species the tooltip list splits into two columns.
const TWO_COLUMN_THRESHOLD = 14
// The tooltip moves to the left edge when the pointer gets this close to it.
const TOOLTIP_CLEARANCE = 10

const chartHeight = computed(() => Math.max(220, props.species.length * 30 + 130))

const columnTotals = computed(() =>
  HOURS.map((hour) => props.species.reduce((sum, entry) => sum + entry.hours[hour], 0)),
)

const option = computed(() => {
  const columnHighlight = {
    show: true,
    type: 'shadow',
    triggerTooltip: false,
    label: { show: false },
    shadowStyle: { color: CHART_COLORS.activityColumnHighlight },
  }

  const baseOption = {
    animation: false,
    grid: [totalsGrid(PLOT_LEFT), heatmapGrid(PLOT_LEFT, HEATMAP_BOTTOM)],
    xAxis: [
      totalsXAxis(HOURS, { axisPointer: columnHighlight }),
      {
        gridIndex: 1,
        type: 'category',
        data: HOURS,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          ...AXIS_TEXT,
          interval: 2,
          formatter: (hour) => formatHourOfDay(Number(hour)),
        },
        axisPointer: columnHighlight,
      },
    ],
    yAxis: [
      totalsYAxis(t),
      {
        gridIndex: 1,
        type: 'category',
        inverse: true,
        data: props.species.map((entry) => entry.common_name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          ...AXIS_TEXT,
          interval: 0,
          margin: LABEL_GAP,
          width: LABEL_WIDTH,
          overflow: 'break',
        },
      },
    ],
    // The pointer highlights the hour in both the bars and the heatmap.
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    visualMap: activityLegend(t),
    tooltip: {
      trigger: 'item',
      className: 'hour-tooltip',
      ...TOOLTIP_STYLE,
      padding: [8, 10],
      textStyle: { fontFamily: HEADER_FONT },
      extraCssText: `${TOOLTIP_STYLE.extraCssText} max-width: calc(100vw - 24px);`,
      confine: true,
      position: tooltipPosition,
      formatter: tooltipHtml,
    },
    series: [
      totalsSeries(columnTotals.value, columnTotals.value.map(formatValue), {
        emphasis: { itemStyle: { color: CHART_COLORS.activityBarStrong }, label: { show: true } },
      }),
      heatmapSeries(
        props.species.flatMap((entry, speciesIndex) => {
          // Each row is shaded against its own maximum so every species' daily rhythm
          // is visible regardless of how abundant it is; the totals bars above carry
          // the absolute per-hour volume.
          const rowMaximum = Math.max(...entry.hours, 1)
          return entry.hours.map((count, hour) => [
            hour,
            speciesIndex,
            activityLevel(count, rowMaximum),
            count,
          ])
        }),
      ),
    ],
  }

  const narrowOption = {
    grid: [{ left: NARROW_PLOT_LEFT }, { left: NARROW_PLOT_LEFT }],
    xAxis: [{}, { axisLabel: { interval: 5 } }],
    yAxis: [{}, { axisLabel: { width: NARROW_LABEL_WIDTH } }],
    series: [{ label: { show: false } }],
  }

  // The settings at the top level, plus the narrow-chart rules applied on top of them.
  return { ...baseOption, media: [{ query: { maxWidth: NARROW_WIDTH }, option: narrowOption }] }
})

function formatValue(count) {
  if (metric.value === 'total' || count === 0) return String(count)
  const average = count / props.days
  if (average >= 10) return String(Math.round(average))
  // A species detected once or twice over a long period still rounds to 0.0,
  // which reads as "never heard" next to its name in the tooltip.
  if (average < 0.05) return '<0.1'
  return average.toFixed(1)
}

function countUnit(count) {
  // Zero is zero whichever metric is showing, and "0.0 detections per day"
  // reads like a rounding artefact rather than a plain absence.
  if (count === 0) return t('chart.detections')
  if (metric.value === 'daily') return t('chart.detectionsPerDay')
  return count !== 1 ? t('chart.detections') : t('chart.detection')
}

function summaryLabel(total) {
  if (metric.value === 'daily') {
    return `${t('chart.metricDailyAverage')}: ${formatValue(total)} ${t('chart.detectionsPerDay')}`
  }
  return `${t('chart.totalDetections')}: ${total}`
}

/*
 * The card for the hour under the pointer. Rows follow the Y axis, species for
 * species, so a name sits in the same place whichever hour is hovered, and the
 * row under the pointer is marked. Over the totals bars there is no row.
 */
function tooltipHtml(params) {
  const isCell = params.seriesType === 'heatmap'
  const hour = isCell ? params.value[0] : params.dataIndex
  const hoveredSpecies = isCell ? params.value[1] : null
  const total = columnTotals.value[hour]
  const header =
    `<div class="hour-tooltip__header">` +
    `<div class="hour-tooltip__hour" style="color: ${CHART_COLORS.tooltip.title}">` +
    `${format.encodeHTML(`${t('chart.hour')}: ${formatHourOfDay(hour)}`)}</div>` +
    `<div class="hour-tooltip__total" style="color: ${CHART_COLORS.tooltip.body}">` +
    `${format.encodeHTML(summaryLabel(total))}</div></div>`

  if (total === 0) {
    return (
      header +
      `<div class="hour-tooltip__empty" style="color: ${CHART_COLORS.tooltip.body}">` +
      `${format.encodeHTML(t('chart.noDetections'))}</div>`
    )
  }

  const rows = props.species.map((entry, speciesIndex) => {
    const count = entry.hours[hour]
    const active = speciesIndex === hoveredSpecies ? ' hour-tooltip__row--active' : ''
    const nameColor = count === 0 ? CHART_COLORS.axis : CHART_COLORS.tooltip.body
    const countColor = count === 0 ? CHART_COLORS.axis : CHART_COLORS.tooltip.title
    return (
      `<div class="hour-tooltip__row${active}">` +
      `<span class="hour-tooltip__name" style="color: ${nameColor}">` +
      `${format.encodeHTML(entry.common_name)}</span>` +
      `<span class="hour-tooltip__count" style="color: ${countColor}">` +
      `${format.encodeHTML(`${formatValue(count)} ${countUnit(count)}`)}</span></div>`
    )
  })
  const split = rows.length > TWO_COLUMN_THRESHOLD ? ' hour-tooltip__rows--split' : ''
  return `${header}<div class="hour-tooltip__rows${split}">${rows.join('')}</div>`
}

/*
 * Pinned to the top of the heatmap instead of trailing the pointer, so the card
 * holds still while you sweep across the hours. It rests on the right and moves
 * to the left edge once the pointer would end up underneath it.
 */
function tooltipPosition(point, params, element, rect, size) {
  const [chartWidth] = size.viewSize
  const pinnedRight = chartWidth - size.contentSize[0]
  const pinnedLeft = chartWidth > NARROW_WIDTH ? PLOT_LEFT : NARROW_PLOT_LEFT
  const clearsPointer = point[0] < pinnedRight - TOOLTIP_CLEARANCE
  return [clearsPointer ? pinnedRight : pinnedLeft, HEATMAP_TOP]
}
</script>

<style>
/* Tooltip card built by tooltipHtml(); ECharts renders it outside the scoped tree. */
.hour-tooltip__header {
  margin-bottom: 6px;
}
.hour-tooltip__hour {
  font-size: 13px;
  font-weight: 600;
}
.hour-tooltip__total {
  font-size: 12px;
}
.hour-tooltip__empty {
  font-size: 12px;
}
.hour-tooltip__rows {
  margin: 0 -5px;
}
.hour-tooltip__rows--split {
  column-count: 2;
  column-gap: 14px;
}
.hour-tooltip__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  break-inside: avoid;
  padding: 2px 5px;
  border-radius: 2px;
}
/* Species row the pointer is on, to find it among a long list. */
.hour-tooltip__row--active {
  background: rgba(255, 255, 255, 0.13);
}
.hour-tooltip__name {
  font-family: var(--font-serif);
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hour-tooltip__count {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  flex-shrink: 0;
}
@media (max-width: 575.98px) {
  .hour-tooltip__rows--split {
    column-count: 1;
  }
  .hour-tooltip__name {
    font-size: 13px;
  }
}
</style>
