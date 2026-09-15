<template>
  <div class="chart-card p-3">
    <div class="chart-label mb-2">{{ t('chart.heatmap') }}</div>
    <div style="position: relative; height: 300px">
      <canvas ref="canvas"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart, CategoryScale, LinearScale, Tooltip } from 'chart.js'
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix'
import dayjs from 'dayjs'
import { CHART_COLORS, TOOLTIP_DEFAULTS } from '../../chartColors.js'
import { HEATMAP_HEADER_HEIGHT, createHeatmapHeaderPlugin } from './heatmapHeader.js'

const { t } = useI18n()

Chart.register(CategoryScale, LinearScale, Tooltip, MatrixController, MatrixElement)

const props = defineProps({
  heatmap: { type: Array, required: true },
  xLabels: { type: Array, required: true },
  granularity: { type: String, required: true },
})

const canvas = ref(null)
let chart = null

// One total per column, in the order of xLabels.
let columnTotals = []
const headerPlugin = createHeatmapHeaderPlugin({ t, getColumnTotals: () => columnTotals })

function render() {
  if (!canvas.value || !props.xLabels.length) return
  if (chart) {
    chart.destroy()
    chart = null
  }

  const lookup = {}
  let max = 1
  props.heatmap.forEach((cell) => {
    lookup[`${cell.x}|${cell.y}`] = cell.v
    if (cell.v > max) max = cell.v
  })

  const fmtX = (x) =>
    props.granularity === 'day' ? dayjs(x).format('L') : dayjs(x).format('MMM YYYY')
  const displayLabels = props.xLabels.map(fmtX)
  const xCount = props.xLabels.length

  const gridData = props.xLabels.flatMap((x, xi) =>
    Array.from({ length: 24 }, (_, h) => ({
      x: displayLabels[xi],
      y: h,
      v: lookup[`${x}|${h}`] ?? 0,
      raw: x,
    })),
  )

  const totalsByLabel = {}
  props.heatmap.forEach(({ x, v }) => {
    const label = fmtX(x)
    totalsByLabel[label] = (totalsByLabel[label] ?? 0) + v
  })
  columnTotals = displayLabels.map((label) => totalsByLabel[label] ?? 0)

  const minorGridPlugin = {
    id: 'activityMinorGrid',
    afterDraw(ch) {
      const yAxis = ch.scales.y
      const { left, right } = ch.chartArea
      const ctx = ch.ctx
      ctx.save()
      ctx.strokeStyle = CHART_COLORS.activityGridMinor
      ctx.lineWidth = 1
      ;[3, 9, 15, 21].forEach((hour) => {
        const y = yAxis.getPixelForValue(hour)
        ctx.beginPath()
        ctx.moveTo(left, y)
        ctx.lineTo(right, y)
        ctx.stroke()
      })
      ctx.restore()
    },
  }

  chart = new Chart(canvas.value, {
    type: 'matrix',
    plugins: [headerPlugin, minorGridPlugin],
    data: {
      datasets: [
        {
          data: gridData,
          backgroundColor(ctx) {
            const v = ctx.dataset.data[ctx.dataIndex]?.v ?? 0
            if (v === 0) return CHART_COLORS.heatmapEmptyCell
            const index = Math.min(4, Math.floor((v / max) * 5))
            return CHART_COLORS.heatmapPalette[index]
          },
          borderWidth: 0,
          width({ chart }) {
            const a = chart.chartArea
            return a ? Math.max(1, (a.right - a.left) / xCount - 1) : 5
          },
          height({ chart }) {
            const a = chart.chartArea
            return a ? Math.max(1, (a.bottom - a.top) / 24 - 1) : 5
          },
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      layout: { padding: { top: HEATMAP_HEADER_HEIGHT } },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...TOOLTIP_DEFAULTS,
          callbacks: {
            title: (items) => {
              const cell = items[0].dataset.data[items[0].dataIndex]
              return props.granularity === 'day'
                ? dayjs(cell.raw).format('ll')
                : dayjs(cell.raw).format('MMMM YYYY')
            },
            label: (item) => {
              const cell = item.dataset.data[item.dataIndex]
              const period = cell.y < 12 ? 'AM' : 'PM'
              const hour = cell.y % 12 || 12
              return `${hour}${period} — ${cell.v} ${cell.v !== 1 ? t('chart.detections') : t('chart.detection')}`
            },
          },
        },
      },
      scales: {
        x: {
          type: 'category',
          labels: displayLabels,
          offset: true,
          grid: { display: false },
          ticks: {
            maxTicksLimit: 12,
            font: { size: 12 },
            color: CHART_COLORS.axis,
          },
          border: { display: false },
        },
        y: {
          type: 'linear',
          min: -0.5,
          max: 23.5,
          reverse: true,
          offset: false,
          grid: { color: CHART_COLORS.activityGridMajor },
          border: { display: false },
          afterBuildTicks: (axis) => {
            axis.ticks = [0, 6, 12, 18].map((v) => ({ value: v }))
          },
          ticks: {
            font: { size: 12 },
            color: CHART_COLORS.axis,
            callback: (h) => {
              const period = h < 12 ? 'AM' : 'PM'
              const hour = h % 12 || 12
              return `${hour}${period}`
            },
          },
        },
      },
    },
  })
}

onMounted(render)
onUnmounted(() => chart?.destroy())
watch(() => props.heatmap, render)
</script>
