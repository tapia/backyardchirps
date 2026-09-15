<template>
  <div class="stat-card-warm p-3">
    <VChart :option="option" :style="{ height: chartHeight + 'px' }" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { use, format } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { CHART_COLORS } from '../../chartColors.js'
import { formatTimelineLabel, timelineLabelIndexes, wrapSpeciesLabel } from './chartLabels.js'

use([CanvasRenderer, GridComponent, LineChart, TooltipComponent])

const { t } = useI18n()

const props = defineProps({
  // [{ common_name, data: [{ day, count }] }], every species over the same columns.
  series: { type: Array, required: true },
  granularity: { type: String, required: true },
})

// Canvas text cannot read CSS custom properties, so the font stack is written out.
const AXIS_FONT = "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif"
const AXIS_TEXT = { color: CHART_COLORS.axis, fontSize: 13, fontFamily: AXIS_FONT }

// Room for species names, wrapped at 14 characters, which end this far from the plot.
const LABEL_WIDTH = 90
const LABEL_GAP = 16
const PLOT_LEFT = LABEL_WIDTH + LABEL_GAP + 8
const PLOT_TOP = 16
const PLOT_BOTTOM = 30
// Room for the end of the last date label, which is centred on its column.
const PLOT_RIGHT = 16
// Date labels start this far below the plot.
const DATE_LABEL_GAP = 11
// The widest point of any ridge fills this share of its row, half above the baseline and half below.
const RIDGE_ROW_SHARE = 0.88
const BASELINE_WIDTH = 2

const chartHeight = computed(() => Math.max(160, props.series.length * 52 + 60))

/*
 * One plot area per species, stacked in rows. Each has its own axes: a baseline
 * in the species colour through the middle of the row, and a count scale shared
 * by every row, so a ridge's height compares across species. Each ridge is two
 * filled lines, the counts above the baseline and the same counts mirrored below.
 */
const option = computed(() => {
  const dates = props.series[0].data.map((point) =>
    formatTimelineLabel(point.day, props.granularity),
  )
  const labelledDates = new Set(timelineLabelIndexes(dates.length, props.granularity))
  const maxCount = Math.max(
    1,
    ...props.series.flatMap((species) => species.data.map((point) => point.count)),
  )
  const countLimit = maxCount / RIDGE_ROW_SHARE
  const rowHeight = (chartHeight.value - PLOT_TOP - PLOT_BOTTOM) / props.series.length
  const lastRow = props.series.length - 1

  return {
    animation: false,
    grid: props.series.map((species, row) => ({
      left: PLOT_LEFT,
      right: PLOT_RIGHT,
      top: PLOT_TOP + row * rowHeight,
      height: rowHeight,
      outerBoundsMode: 'none',
    })),
    xAxis: [
      ...props.series.map((species, row) => ({
        gridIndex: row,
        type: 'category',
        data: dates,
        axisLine: { onZero: true, lineStyle: { color: speciesColor(row), width: BASELINE_WIDTH } },
        axisTick: { show: false },
        axisLabel: { show: false },
      })),
      // The dates, under the last row.
      {
        gridIndex: lastRow,
        type: 'category',
        data: dates,
        position: 'bottom',
        axisLine: { show: false, onZero: false },
        axisTick: { show: false },
        axisPointer: { show: false },
        axisLabel: {
          ...AXIS_TEXT,
          margin: DATE_LABEL_GAP,
          hideOverlap: true,
          alignMaxLabel: 'right',
          interval: (index) => labelledDates.has(index),
        },
      },
    ],
    yAxis: props.series.map((species, row) => ({
      gridIndex: row,
      type: 'value',
      min: -countLimit,
      max: countLimit,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
      // ECharts wraps axis labels but not axis names, so the line breaks are added here.
      name: wrapSpeciesLabel(species.common_name),
      nameLocation: 'middle',
      nameRotate: 0,
      nameGap: LABEL_GAP,
      nameTextStyle: { ...AXIS_TEXT, align: 'right', verticalAlign: 'middle', lineHeight: 15.6 },
    })),
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'none' },
      backgroundColor: CHART_COLORS.tooltip.background,
      borderColor: CHART_COLORS.tooltip.border,
      borderWidth: 1,
      padding: 10,
      textStyle: { color: CHART_COLORS.tooltip.body, fontSize: 12, fontFamily: AXIS_FONT },
      extraCssText: 'border-radius: 2px; box-shadow: none;',
      formatter: tooltipHtml,
    },
    series: props.series.flatMap((species, row) => {
      const counts = species.data.map((point) => point.count)
      return [
        ridgeHalf(row, counts),
        ridgeHalf(
          row,
          counts.map((count) => -count),
        ),
      ]
    }),
  }
})

function speciesColor(row) {
  return CHART_COLORS.palette[row % CHART_COLORS.palette.length]
}

/*
 * Half a ridge, filled from the baseline. With smoothMonotone 'x' and smooth 0.5
 * the curve leaves and reaches every point level, bending halfway between them.
 */
function ridgeHalf(row, values) {
  return {
    type: 'line',
    xAxisIndex: row,
    yAxisIndex: row,
    data: values,
    smooth: 0.5,
    smoothMonotone: 'x',
    symbol: 'none',
    lineStyle: { width: 0 },
    areaStyle: { color: speciesColor(row), opacity: 1 },
  }
}

function tooltipHtml(params) {
  const first = params[0]
  if (!first) return ''
  // Two series per species: the upper and the mirrored half.
  const row = Math.floor(first.seriesIndex / 2)
  const species = props.series[row]
  const point = species.data[first.dataIndex]
  const unit = point.count !== 1 ? t('chart.detections') : t('chart.detection')
  return (
    `<div class="chart-tooltip-title" style="color: ${CHART_COLORS.tooltip.title}">` +
    `${format.encodeHTML(formatTimelineLabel(point.day, props.granularity))}</div>` +
    `<span class="chart-tooltip-swatch" style="background: ${speciesColor(row)}"></span>` +
    format.encodeHTML(`${species.common_name}: ${point.count} ${unit}`)
  )
}
</script>
