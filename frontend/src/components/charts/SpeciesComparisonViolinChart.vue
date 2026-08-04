<template>
  <div class="stat-card-warm p-3">
    <div :style="{ position: 'relative', height: chartHeight + 'px' }">
      <canvas ref="canvas"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart, ScatterController, PointElement, LinearScale, Tooltip } from 'chart.js'
import dayjs from 'dayjs'
import { CHART_COLORS, TOOLTIP_DEFAULTS } from '../../chartColors.js'
import { wrapSpeciesLabel } from './chartLabels.js'

Chart.register(ScatterController, PointElement, LinearScale, Tooltip)

const { t } = useI18n()

const props = defineProps({
  series: { type: Array, required: true },
  granularity: { type: String, required: true },
})

const canvas = ref(null)
let chart = null

const chartHeight = computed(() => Math.max(160, props.series.length * 52 + 60))

function hexToRgba(hex, alpha) {
  const red = parseInt(hex.slice(1, 3), 16)
  const green = parseInt(hex.slice(3, 5), 16)
  const blue = parseInt(hex.slice(5, 7), 16)
  return `rgba(${red},${green},${blue},${alpha})`
}

function formatLabel(d) {
  if (props.granularity === 'hour') return dayjs(d).format('hA')
  if (props.granularity === 'month') return dayjs(d).format('MMM YYYY')
  return dayjs(d).format('L')
}

function buildDatasets() {
  return props.series.map((species, speciesIndex) => ({
    label: species.common_name,
    data: species.data.map((point, timeIndex) => ({ x: timeIndex, y: speciesIndex })),
    pointRadius: 0,
    pointHoverRadius: 0,
  }))
}

function render() {
  if (chart) {
    chart.destroy()
    chart = null
  }
  if (!canvas.value || !props.series.length) return

  const timeLabels = props.series[0].data.map((point) => formatLabel(point.day))
  const speciesCount = props.series.length
  const timeCount = timeLabels.length

  const rowLinesPlugin = {
    id: 'rowLines',
    beforeDraw(instance) {
      const { ctx, chartArea, scales } = instance
      if (!chartArea) return
      ctx.save()
      ctx.lineWidth = 2
      props.series.forEach((species, speciesIndex) => {
        const color = CHART_COLORS.palette[speciesIndex % CHART_COLORS.palette.length]
        const yPixel = scales.y.getPixelForValue(speciesIndex)
        ctx.strokeStyle = color
        ctx.beginPath()
        ctx.moveTo(chartArea.left, yPixel)
        ctx.lineTo(chartArea.right, yPixel)
        ctx.stroke()
      })
      ctx.restore()
    },
  }

  const violinPlugin = {
    id: 'violins',
    afterDatasetsDraw(instance) {
      const { ctx, scales, chartArea } = instance
      if (!chartArea) return

      const maxCount = Math.max(
        ...props.series.flatMap((species) => species.data.map((point) => point.count)),
        1,
      )
      const rowHeight = chartArea.height / speciesCount
      const maxAmplitude = rowHeight * 0.44

      props.series.forEach((species, speciesIndex) => {
        const color = CHART_COLORS.palette[speciesIndex % CHART_COLORS.palette.length]
        const centerY = scales.y.getPixelForValue(speciesIndex)
        const xCoords = species.data.map((point, timeIndex) => scales.x.getPixelForValue(timeIndex))
        const amplitudes = species.data.map((point) => (point.count / maxCount) * maxAmplitude)

        if (xCoords.length < 2) return

        ctx.save()
        ctx.beginPath()
        ctx.moveTo(xCoords[0], centerY - amplitudes[0])
        for (let pointIndex = 1; pointIndex < xCoords.length; pointIndex++) {
          const controlX = (xCoords[pointIndex - 1] + xCoords[pointIndex]) / 2
          ctx.bezierCurveTo(
            controlX,
            centerY - amplitudes[pointIndex - 1],
            controlX,
            centerY - amplitudes[pointIndex],
            xCoords[pointIndex],
            centerY - amplitudes[pointIndex],
          )
        }
        ctx.lineTo(xCoords[xCoords.length - 1], centerY + amplitudes[xCoords.length - 1])
        for (let pointIndex = xCoords.length - 1; pointIndex >= 1; pointIndex--) {
          const controlX = (xCoords[pointIndex] + xCoords[pointIndex - 1]) / 2
          ctx.bezierCurveTo(
            controlX,
            centerY + amplitudes[pointIndex],
            controlX,
            centerY + amplitudes[pointIndex - 1],
            xCoords[pointIndex - 1],
            centerY + amplitudes[pointIndex - 1],
          )
        }
        ctx.closePath()

        ctx.fillStyle = hexToRgba(color, 1)
        ctx.fill()
        ctx.restore()
      })
    },
  }

  chart = new Chart(canvas.value, {
    type: 'scatter',
    data: { datasets: buildDatasets() },
    plugins: [rowLinesPlugin, violinPlugin],
    options: {
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'nearest', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...TOOLTIP_DEFAULTS,
          callbacks: {
            title: (items) => {
              const timeIndex = items[0].dataIndex
              const day = props.series[items[0].datasetIndex]?.data[timeIndex]?.day
              return day ? formatLabel(day) : ''
            },
            label: (item) => {
              const series = props.series[item.datasetIndex]
              const point = series?.data[item.dataIndex]
              const count = point?.count ?? 0
              return `${series?.common_name}: ${count} ${count !== 1 ? t('chart.detections') : t('chart.detection')}`
            },
          },
        },
      },
      scales: {
        x: {
          type: 'linear',
          min: -0.5,
          max: timeCount - 0.5,
          afterBuildTicks: (scale) => {
            const maxLabels = props.granularity === 'hour' ? timeCount : 8
            const step = Math.max(1, Math.ceil(timeCount / maxLabels))
            const tickCount = Math.ceil(timeCount / step)
            scale.ticks = [...Array(tickCount).keys()]
              .map((tickIndex) => ({ value: tickIndex * step }))
              .filter((tick) => tick.value < timeCount)
          },
          grid: { display: false },
          border: { display: false },
          ticks: {
            font: { size: 13 },
            color: CHART_COLORS.axis,
            callback: (value) => timeLabels[value] ?? '',
          },
        },
        y: {
          type: 'linear',
          min: -0.5,
          max: speciesCount - 0.5,
          reverse: true,
          afterBuildTicks: (scale) => {
            scale.ticks = [...Array(speciesCount).keys()].map((speciesIndex) => ({
              value: speciesIndex,
            }))
          },
          grid: { display: false },
          border: { display: false },
          ticks: {
            font: { size: 13 },
            color: CHART_COLORS.axis,
            padding: 8,
            callback: (value) => {
              if (value >= 0 && value < speciesCount) {
                return wrapSpeciesLabel(props.series[value].common_name)
              }
              return ''
            },
          },
        },
      },
    },
  })
}

onMounted(render)
onUnmounted(() => chart?.destroy())
watch([() => props.series, () => props.granularity], render, { deep: true })
</script>
