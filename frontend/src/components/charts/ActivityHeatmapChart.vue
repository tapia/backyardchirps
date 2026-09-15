<template>
  <div class="chart-card p-3">
    <div class="chart-label mb-2">{{ t('chart.heatmap') }}</div>
    <VChart class="activity-heatmap" :option="option" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { use, format } from 'echarts/core'
import { BarChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapPiecewiseComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import { CHART_COLORS } from '../../chartColors.js'
import { formatHourOfDay } from './chartLabels.js'
import {
  AXIS_FONT,
  AXIS_TEXT,
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
  BarChart,
  CanvasRenderer,
  GridComponent,
  HeatmapChart,
  TooltipComponent,
  VisualMapPiecewiseComponent,
])

const { t } = useI18n()

const props = defineProps({
  // [{ x: day or month, y: hour, v: count }]
  heatmap: { type: Array, required: true },
  xLabels: { type: Array, required: true },
  granularity: { type: String, required: true },
})

const HOURS = Array.from({ length: 24 }, (unused, hour) => hour)

const PLOT_LEFT = 46
const HEATMAP_BOTTOM = 28
// The hours that get a label and a short tick: 12AM, 6AM, 12PM and 6PM.
const HOUR_LABEL_INTERVAL = 5
const HOUR_TICK_LENGTH = 8
// Hour labels end this far from the heatmap: the tick plus a small gap.
const HOUR_LABEL_GAP = HOUR_TICK_LENGTH + 3

const option = computed(() => {
  const columns = props.xLabels.map(formatColumn)
  const counts = new Map(props.heatmap.map((cell) => [`${cell.x}|${cell.y}`, cell.v]))
  // One scale for the whole map, unlike the species-by-hour heatmap.
  const maximum = Math.max(1, ...props.heatmap.map((cell) => cell.v))
  const totals = props.xLabels.map((x) =>
    HOURS.reduce((sum, hour) => sum + (counts.get(`${x}|${hour}`) ?? 0), 0),
  )

  return {
    baseOption: {
      animation: false,
      grid: [totalsGrid(PLOT_LEFT), heatmapGrid(PLOT_LEFT, HEATMAP_BOTTOM)],
      xAxis: [
        totalsXAxis(columns),
        {
          gridIndex: 1,
          type: 'category',
          data: columns,
          axisLine: { show: false },
          axisTick: { show: false },
          // The first and last dates sit inside the plot instead of centred on their column.
          axisLabel: { ...AXIS_TEXT, alignMinLabel: 'left', alignMaxLabel: 'right' },
        },
      ],
      yAxis: [
        totalsYAxis(t, HOUR_LABEL_GAP),
        {
          gridIndex: 1,
          type: 'category',
          inverse: true,
          data: HOURS,
          axisLine: { show: false },
          axisTick: {
            show: true,
            interval: HOUR_LABEL_INTERVAL,
            alignWithLabel: true,
            length: HOUR_TICK_LENGTH,
            lineStyle: { color: CHART_COLORS.activityHourTick },
          },
          axisLabel: {
            ...AXIS_TEXT,
            interval: HOUR_LABEL_INTERVAL,
            margin: HOUR_LABEL_GAP,
            formatter: (hour) => formatHourOfDay(Number(hour)),
          },
        },
      ],
      visualMap: activityLegend(t),
      tooltip: {
        trigger: 'item',
        backgroundColor: CHART_COLORS.tooltip.background,
        borderColor: CHART_COLORS.tooltip.border,
        borderWidth: 1,
        padding: 10,
        textStyle: { color: CHART_COLORS.tooltip.body, fontSize: 12, fontFamily: AXIS_FONT },
        extraCssText: 'border-radius: 2px; box-shadow: none;',
        formatter: tooltipHtml,
      },
      series: [
        totalsSeries(totals, totals.map(String), { silent: true }),
        heatmapSeries(
          props.xLabels.flatMap((x, column) =>
            HOURS.map((hour) => {
              const count = counts.get(`${x}|${hour}`) ?? 0
              return [column, hour, activityLevel(count, maximum), count]
            }),
          ),
        ),
      ],
    },
    media: [
      {
        query: { maxWidth: narrowBarsWidth(PLOT_LEFT, columns.length) },
        option: { series: [{ label: { show: false } }] },
      },
    ],
  }
})

function formatColumn(x) {
  return props.granularity === 'day' ? dayjs(x).format('L') : dayjs(x).format('MMM YYYY')
}

function tooltipHtml(params) {
  const [column, hour, , count] = params.value
  const period = dayjs(props.xLabels[column]).format(
    props.granularity === 'day' ? 'll' : 'MMMM YYYY',
  )
  const unit = count !== 1 ? t('chart.detections') : t('chart.detection')
  return (
    `<div class="activity-tooltip__title" style="color: ${CHART_COLORS.tooltip.title}">` +
    `${format.encodeHTML(period)}</div>` +
    `<span class="chart-tooltip-swatch" style="background: ${params.color}"></span>` +
    `${format.encodeHTML(`${formatHourOfDay(hour)}: ${count} ${unit}`)}`
  )
}
</script>

<style>
.activity-heatmap {
  height: 300px;
}

/* Tooltip built by tooltipHtml(); ECharts renders it outside the scoped tree. */
.activity-tooltip__title {
  font-weight: bold;
  margin-bottom: 6px;
}
</style>
