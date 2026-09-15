<template>
  <div class="chart-card p-3 h-100 d-flex flex-column">
    <div class="chart-label mb-2">{{ t('chart.byHourOfDay') }}</div>
    <VChart class="polar-chart" :option="option" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { use, format } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { PolarComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { CHART_COLORS } from '../../chartColors.js'
import { formatHourOfDay } from './chartLabels.js'

use([BarChart, CanvasRenderer, PolarComponent, TooltipComponent])

const { t } = useI18n()

const props = defineProps({
  // 24 counts, one per hour of the day from midnight.
  hourly: { type: Array, required: true },
})

const HOURS = Array.from({ length: 24 }, (unused, hour) => hour)

// Canvas text cannot read CSS custom properties, so the font stack is written out.
const AXIS_FONT = "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif"

// Share of the space left by the hour labels that the circle fills.
const RADIUS = '84%'
// Midnight's wedge is centred at the top and the hours run clockwise.
const START_ANGLE = 90 + 360 / 24 / 2
const HOUR_LABEL_GAP = 5
const RINGS = 4
// The quietest hour is drawn at this opacity, the busiest at full strength.
const MIN_OPACITY = 0.2

const option = computed(() => {
  const maximum = Math.max(...props.hourly, 1)
  return {
    polar: { radius: RADIUS },
    angleAxis: {
      type: 'category',
      data: HOURS,
      startAngle: START_ANGLE,
      axisLine: { lineStyle: { color: CHART_COLORS.grid } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: {
        color: CHART_COLORS.axis,
        fontSize: 12,
        fontFamily: AXIS_FONT,
        margin: HOUR_LABEL_GAP,
        formatter: (hour) => formatHourOfDay(Number(hour)),
      },
    },
    radiusAxis: {
      min: 0,
      splitNumber: RINGS,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: CHART_COLORS.grid } },
    },
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
    series: {
      type: 'bar',
      coordinateSystem: 'polar',
      barCategoryGap: 0,
      itemStyle: { borderColor: CHART_COLORS.polarBorder, borderWidth: 1 },
      data: props.hourly.map((count) => ({
        value: count,
        itemStyle: { color: wedgeColor(count, maximum) },
      })),
    },
  }
})

// Busier hours are drawn more opaque.
function wedgeColor(count, maximum) {
  const opacity = MIN_OPACITY + (count / maximum) * (1 - MIN_OPACITY)
  return `rgba(${CHART_COLORS.densityRgb}, ${opacity.toFixed(2)})`
}

function tooltipHtml(params) {
  const unit = params.value !== 1 ? t('chart.detections') : t('chart.detection')
  return (
    `<span class="chart-tooltip-swatch" style="background: ${params.color}"></span>` +
    format.encodeHTML(`${params.value} ${unit}`)
  )
}
</script>

<style scoped>
/* Fill the card so it matches the height of the activity map beside it (desktop). */
.polar-chart {
  flex: 1 1 auto;
  min-height: 260px;
}
</style>
