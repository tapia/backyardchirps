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

const { t } = useI18n()

Chart.register(CategoryScale, LinearScale, Tooltip, MatrixController, MatrixElement)

const props = defineProps({
  heatmap: { type: Array, required: true },
  xLabels: { type: Array, required: true },
  granularity: { type: String, required: true },
})

const canvas = ref(null)
let chart = null

const PADDING_TOP = 78
const BAR_MAX_H = 36
const BAR_BASE_OFFSET = 10
const LABEL_FONT = "10px 'Source Sans 3', system-ui, sans-serif"
const VALUE_LABEL_FONT = "bold 12px 'Source Sans 3', system-ui, sans-serif"

function topRoundedRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h)
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h)
  ctx.lineTo(x, y + h)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}

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

  const columnTotals = {}
  props.heatmap.forEach(({ x, v }) => {
    const label = fmtX(x)
    columnTotals[label] = (columnTotals[label] ?? 0) + v
  })
  const maxTotal = Math.max(...Object.values(columnTotals), 1)

  const barsPlugin = {
    id: 'activityBars',
    afterDraw(ch) {
      const xScale = ch.scales.x
      const { top: areaTop, left: areaLeft, right: areaRight } = ch.chartArea
      const ctx = ch.ctx
      const barWidth = Math.max(1, (areaRight - areaLeft) / xCount - 1)
      const cornerR = Math.min(4, barWidth / 2)
      const barBase = areaTop - BAR_BASE_OFFSET

      ctx.save()

      displayLabels.forEach((label) => {
        const total = columnTotals[label] ?? 0
        if (total === 0) return
        const xPixel = xScale.getPixelForValue(label)
        const barH = Math.max(2, (total / maxTotal) * BAR_MAX_H)
        const x = xPixel - barWidth / 2
        const y = barBase - barH

        ctx.fillStyle = CHART_COLORS.activityBar
        topRoundedRect(ctx, x, y, barWidth, barH, cornerR)
        ctx.fill()

        if (barWidth >= 18) {
          ctx.fillStyle = CHART_COLORS.axis
          ctx.font = VALUE_LABEL_FONT
          ctx.textAlign = 'center'
          ctx.textBaseline = 'bottom'
          ctx.fillText(total, xPixel, y - 2)
        }
      })

      // Separator between bars and heatmap
      ctx.strokeStyle = CHART_COLORS.activityDivider
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(0, areaTop - 8)
      ctx.lineTo(areaRight, areaTop - 8)
      ctx.stroke()

      // "Totals" Y-axis label, anchored to where Chart.js actually renders tick labels.
      // Chart.js computes x = scale.right - (tickLength + tickPadding) for left-axis labels.
      const yScale = ch.scales.y
      const gridTickLength =
        yScale.options.grid?.drawTicks !== false ? (yScale.options.grid?.tickLength ?? 8) : 0
      const tickPadding = yScale.options.ticks?.padding ?? 3
      const tickAnchorX =
        yScale._labelItems?.[0]?.options?.translation?.[0] ??
        yScale.right - gridTickLength - tickPadding
      const barMidY = areaTop - BAR_BASE_OFFSET - BAR_MAX_H / 2
      ctx.font = "12px 'Source Sans 3', system-ui, sans-serif"
      ctx.fillStyle = CHART_COLORS.axis
      ctx.textAlign = 'right'
      ctx.textBaseline = 'middle'
      ctx.fillText(t('chart.totals'), tickAnchorX, barMidY)

      // Legend (top-right)
      const palette = CHART_COLORS.heatmapPalette
      const swatchSz = 7
      const swatchGap = 3
      ctx.font = LABEL_FONT
      const lessText = t('chart.lessActivity')
      const moreText = t('chart.moreActivity')
      const lessW = ctx.measureText(lessText).width
      const moreW = ctx.measureText(moreText).width
      const swatchesW = palette.length * swatchSz + (palette.length - 1) * swatchGap
      const textGap = 6
      const totalLegendW = lessW + textGap + swatchesW + textGap + moreW
      let lx = areaRight - totalLegendW
      const ly = 5
      const swatchMidY = ly + swatchSz / 2

      ctx.fillStyle = CHART_COLORS.activityLabel
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillText(lessText, lx, swatchMidY)
      lx += lessW + textGap

      palette.forEach((color) => {
        ctx.fillStyle = color
        ctx.fillRect(lx, ly, swatchSz, swatchSz)
        lx += swatchSz + swatchGap
      })

      ctx.fillStyle = CHART_COLORS.activityLabel
      ctx.fillText(moreText, lx + textGap - swatchGap, swatchMidY)

      ctx.restore()
    },
  }

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
    plugins: [barsPlugin, minorGridPlugin],
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
      layout: { padding: { top: PADDING_TOP } },
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
