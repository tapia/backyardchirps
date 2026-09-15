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

// Canvas text cannot read CSS custom properties, so the font stacks are written out.
const AXIS_FONT = "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif"
const HEADER_FONT = "'Source Sans 3', system-ui, sans-serif"

// Layout from the top: the legend, the totals bars, then the heatmap.
const LEGEND_TOP = 5
const BARS_TOP = 32
const BARS_HEIGHT = 36
const HEATMAP_TOP = 78
const HEATMAP_BOTTOM = 28
// Species names wrap to this width, this far from the heatmap.
const LABEL_WIDTH = 100
const LABEL_GAP = 8
const PLOT_LEFT = LABEL_WIDTH + 2 * LABEL_GAP
// Below this chart width the bars are too narrow to carry their values (only the
// hovered one shows it), the hours are labelled every six, and names wrap sooner.
const NARROW_WIDTH = 560
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
  const totalLabels = columnTotals.value.map(formatValue)
  const axisText = { color: CHART_COLORS.axis, fontSize: 12, fontFamily: AXIS_FONT }
  const columnHighlight = {
    show: true,
    type: 'shadow',
    triggerTooltip: false,
    label: { show: false },
    shadowStyle: { color: CHART_COLORS.activityColumnHighlight },
  }

  const baseOption = {
    animation: false,
    grid: [
      { top: BARS_TOP, height: BARS_HEIGHT, left: PLOT_LEFT, right: 0 },
      { top: HEATMAP_TOP, bottom: HEATMAP_BOTTOM, left: PLOT_LEFT, right: 0 },
    ],
    xAxis: [
      {
        gridIndex: 0,
        type: 'category',
        data: HOURS,
        axisLine: { lineStyle: { color: CHART_COLORS.activityDivider } },
        axisTick: { show: false },
        axisLabel: { show: false },
        axisPointer: columnHighlight,
      },
      {
        gridIndex: 1,
        type: 'category',
        data: HOURS,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { ...axisText, interval: 2, formatter: (hour) => hourLabel(Number(hour)) },
        axisPointer: columnHighlight,
      },
    ],
    yAxis: [
      {
        gridIndex: 0,
        type: 'value',
        max: 'dataMax',
        axisLabel: { show: false },
        splitLine: { show: false },
        name: t('chart.totals'),
        nameLocation: 'middle',
        nameRotate: 0,
        nameGap: LABEL_GAP,
        nameTextStyle: { ...axisText, fontFamily: HEADER_FONT, align: 'right' },
      },
      {
        gridIndex: 1,
        type: 'category',
        inverse: true,
        data: props.species.map((entry) => entry.common_name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          ...axisText,
          interval: 0,
          margin: LABEL_GAP,
          width: LABEL_WIDTH,
          overflow: 'break',
        },
      },
    ],
    // The pointer highlights the hour in both the bars and the heatmap.
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    visualMap: {
      type: 'piecewise',
      seriesIndex: 1,
      dimension: 2,
      pieces: CHART_COLORS.heatmapPalette.map((color, index) => ({ value: index + 1, color })),
      outOfRange: { color: CHART_COLORS.heatmapEmptyCell },
      orient: 'horizontal',
      right: 0,
      top: LEGEND_TOP,
      itemWidth: 7,
      itemHeight: 7,
      itemGap: 3,
      itemSymbol: 'rect',
      showLabel: false,
      text: [t('chart.moreActivity'), t('chart.lessActivity')],
      textGap: 6,
      textStyle: { color: CHART_COLORS.activityLabel, fontSize: 10, fontFamily: HEADER_FONT },
      selectedMode: false,
      hoverLink: false,
    },
    tooltip: {
      trigger: 'item',
      className: 'hour-tooltip',
      backgroundColor: CHART_COLORS.tooltip.background,
      borderColor: CHART_COLORS.tooltip.border,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { fontFamily: HEADER_FONT },
      extraCssText: 'border-radius: 2px; box-shadow: none; max-width: calc(100vw - 24px);',
      confine: true,
      position: tooltipPosition,
      formatter: tooltipHtml,
    },
    series: [
      {
        type: 'bar',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: columnTotals.value.map((total) => total || null),
        barCategoryGap: 1,
        barMinHeight: 2,
        itemStyle: { color: CHART_COLORS.activityBar, borderRadius: [4, 4, 0, 0] },
        label: {
          show: true,
          position: 'top',
          distance: 2,
          formatter: ({ dataIndex }) => totalLabels[dataIndex],
          color: CHART_COLORS.axis,
          fontSize: 12,
          fontWeight: 'bold',
          fontFamily: HEADER_FONT,
        },
        emphasis: { itemStyle: { color: CHART_COLORS.activityBarStrong }, label: { show: true } },
      },
      {
        type: 'heatmap',
        xAxisIndex: 1,
        yAxisIndex: 1,
        // [hour, species row, colour step, count]
        data: props.species.flatMap((entry, speciesIndex) => {
          // Each row is shaded against its own maximum so every species' daily rhythm
          // is visible regardless of how abundant it is; the totals bars above carry
          // the absolute per-hour volume.
          const rowMaximum = Math.max(...entry.hours, 1)
          return entry.hours.map((count, hour) => [
            hour,
            speciesIndex,
            count === 0 ? 0 : Math.min(4, Math.floor((count / rowMaximum) * 5)) + 1,
            count,
          ])
        }),
        itemStyle: { borderColor: CHART_COLORS.heatmapCellGap, borderWidth: 1 },
        emphasis: { disabled: true },
      },
    ],
  }

  const narrowOption = {
    grid: [{ left: NARROW_PLOT_LEFT }, { left: NARROW_PLOT_LEFT }],
    xAxis: [{}, { axisLabel: { interval: 5 } }],
    yAxis: [{}, { axisLabel: { width: NARROW_LABEL_WIDTH } }],
    series: [{ label: { show: false } }],
  }

  return { baseOption, media: [{ query: { maxWidth: NARROW_WIDTH }, option: narrowOption }] }
})

function hourLabel(hour) {
  const period = hour < 12 ? 'AM' : 'PM'
  return `${hour % 12 || 12}${period}`
}

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
    `${format.encodeHTML(`${t('chart.hour')}: ${hourLabel(hour)}`)}</div>` +
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
