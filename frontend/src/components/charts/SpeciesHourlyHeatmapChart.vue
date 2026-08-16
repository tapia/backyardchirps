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
    <div :style="{ position: 'relative', height: chartHeight + 'px' }">
      <canvas ref="canvas"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart, LinearScale } from 'chart.js'
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix'
import { CHART_COLORS } from '../../chartColors.js'
import { wrapSpeciesLabel } from './chartLabels.js'
import { createHourColumnTooltip } from './hourColumnTooltip.js'

const { t } = useI18n()

Chart.register(LinearScale, MatrixController, MatrixElement)

const props = defineProps({
  // [{ scientific_name, common_name, image_url, total, hours: [24 ints] }]
  species: { type: Array, required: true },
  // Days the selected period spans, for the daily-average metric.
  days: { type: Number, required: true },
})

const canvas = ref(null)
let chart = null
let tooltip = null
// Hour under the pointer, or null when it is away from the plot. Drives both
// the column highlight and the tooltip; the chart is redrawn when it changes.
let hoveredHour = null

const metric = ref('total')

const PADDING_TOP = 78
const BAR_MAX_H = 36
const BAR_BASE_OFFSET = 10
// How far above the heatmap the highlight band reaches: past the bars and
// their value labels, but clear of the legend.
const HIGHLIGHT_TOP_OFFSET = BAR_BASE_OFFSET + BAR_MAX_H + 18
const HIGHLIGHT_OUTLINE_WIDTH = 1.5
const LABEL_FONT = "10px 'Source Sans 3', system-ui, sans-serif"
const VALUE_LABEL_FONT = "bold 12px 'Source Sans 3', system-ui, sans-serif"

const chartHeight = computed(() => Math.max(220, props.species.length * 30 + 130))

const columnTotals = computed(() =>
  Array.from({ length: 24 }, (unused, hour) =>
    props.species.reduce((sum, entry) => sum + entry.hours[hour], 0),
  ),
)

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
 * Rows follow the Y axis, species for species, so a name sits in the same place
 * whichever hour is hovered. Species with nothing that hour stay in the list
 * with a zero rather than closing the gap.
 */
function tooltipContent(hour, speciesIndex) {
  const total = columnTotals.value[hour]
  const rows =
    total === 0
      ? []
      : props.species.map((entry, index) => ({
          name: entry.common_name,
          value: `${formatValue(entry.hours[hour])} ${countUnit(entry.hours[hour])}`,
          silent: entry.hours[hour] === 0,
          highlighted: index === speciesIndex,
        }))

  return {
    hourLabel: `${t('chart.hour')}: ${hourLabel(hour)}`,
    totalLabel: summaryLabel(total),
    rows,
    emptyText: t('chart.noDetections'),
  }
}

/*
 * Cell under the pointer as { hour, speciesIndex }, or null when it is outside
 * the plot. The bars sit in the layout padding above the chart area, which
 * Chart.js does not treat as hoverable, so the column is resolved from the raw
 * pointer position instead of the built-in interaction modes; over the bars
 * there is an hour but no species row, and speciesIndex is null.
 */
function cellAtPointer(event) {
  if (!chart) return null
  const { left, right, top, bottom } = chart.chartArea
  const canvasRect = chart.canvas.getBoundingClientRect()
  const pointerX = event.clientX - canvasRect.left
  const pointerY = event.clientY - canvasRect.top
  if (pointerX < left || pointerX > right) return null
  if (pointerY < top - PADDING_TOP || pointerY > bottom) return null

  const hour = Math.round(chart.scales.x.getValueForPixel(pointerX))
  if (!Number.isFinite(hour) || hour < 0 || hour > 23) return null

  const row = Math.round(chart.scales.y.getValueForPixel(pointerY))
  const overRows = pointerY >= top && Number.isFinite(row) && row >= 0 && row < props.species.length
  return { hour, speciesIndex: overRows ? row : null }
}

/*
 * Where the tooltip sits: the edges of the plot, plus where the hovered column
 * falls, so it can pick the edge that leaves that column visible. Lined up with
 * the top of the heatmap, which keeps the totals bars in view. Two resting
 * places rather than a card chasing the pointer.
 */
function tooltipAnchor(hour) {
  const canvasRect = chart.canvas.getBoundingClientRect()
  const { left, right, top } = chart.chartArea

  return {
    left: canvasRect.left + left,
    right: canvasRect.left + right,
    top: canvasRect.top + top,
    columnX: canvasRect.left + chart.scales.x.getPixelForValue(hour),
  }
}

function handlePointerMove(event) {
  const cell = cellAtPointer(event)
  if (cell === null) {
    handlePointerLeave()
    return
  }
  if (cell.hour !== hoveredHour) {
    hoveredHour = cell.hour
    chart.draw()
  }
  tooltip.show(tooltipContent(cell.hour, cell.speciesIndex), tooltipAnchor(cell.hour))
}

function handlePointerLeave() {
  tooltip?.hide()
  if (hoveredHour === null) return
  hoveredHour = null
  chart?.draw()
}

/*
 * Pixel box of the hovered column: the heatmap rows plus the totals bar and its
 * value label above them.
 */
function highlightBounds(ch) {
  const { top: areaTop, bottom: areaBottom, left: areaLeft, right: areaRight } = ch.chartArea
  const columnWidth = (areaRight - areaLeft) / 24
  const centerX = ch.scales.x.getPixelForValue(hoveredHour)

  return {
    x: centerX - columnWidth / 2,
    y: areaTop - HIGHLIGHT_TOP_OFFSET,
    width: columnWidth,
    height: areaBottom - areaTop + HIGHLIGHT_TOP_OFFSET,
  }
}

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
  if (chart) {
    chart.destroy()
    chart = null
  }
  hoveredHour = null
  tooltip?.hide()
  if (!canvas.value || !props.species.length) return

  const speciesCount = props.species.length
  // Each row is shaded against its own maximum so every species' daily rhythm
  // is visible regardless of how abundant it is; the totals bars above carry
  // the absolute per-hour volume.
  const rowMaxima = props.species.map((entry) => Math.max(...entry.hours, 1))
  const maxTotal = Math.max(...columnTotals.value, 1)

  const highlightPlugin = {
    id: 'hourColumnHighlight',
    beforeDatasetsDraw(ch) {
      if (hoveredHour === null) return
      const { x, y, width, height } = highlightBounds(ch)
      const ctx = ch.ctx

      ctx.save()
      ctx.fillStyle = CHART_COLORS.activityColumnHighlight
      ctx.fillRect(x, y, width, height)
      ctx.restore()
    },
    // Drawn last, over the cells and the totals bar: on a busy column the band
    // behind them is invisible, the outline is not.
    afterDraw(ch) {
      if (hoveredHour === null) return
      const { x, y, width, height } = highlightBounds(ch)
      const ctx = ch.ctx

      ctx.save()
      ctx.strokeStyle = CHART_COLORS.activityColumnOutline
      ctx.lineWidth = HIGHLIGHT_OUTLINE_WIDTH
      const inset = HIGHLIGHT_OUTLINE_WIDTH / 2
      ctx.strokeRect(x + inset, y + inset, width - HIGHLIGHT_OUTLINE_WIDTH, height - inset)
      ctx.restore()
    },
  }

  const gridData = props.species.flatMap((entry, speciesIndex) =>
    entry.hours.map((count, hour) => ({ x: hour, y: speciesIndex, v: count })),
  )

  const barsPlugin = {
    id: 'hourlyTotalsBars',
    afterDraw(ch) {
      const xScale = ch.scales.x
      const { top: areaTop, right: areaRight, left: areaLeft } = ch.chartArea
      const ctx = ch.ctx
      const barWidth = Math.max(1, (areaRight - areaLeft) / 24 - 1)
      const cornerR = Math.min(4, barWidth / 2)
      const barBase = areaTop - BAR_BASE_OFFSET

      ctx.save()

      columnTotals.value.forEach((total, hour) => {
        if (total === 0) return
        const isHovered = hour === hoveredHour
        const xPixel = xScale.getPixelForValue(hour)
        const barH = Math.max(2, (total / maxTotal) * BAR_MAX_H)
        const x = xPixel - barWidth / 2
        const y = barBase - barH

        ctx.fillStyle = isHovered ? CHART_COLORS.activityBarStrong : CHART_COLORS.activityBar
        topRoundedRect(ctx, x, y, barWidth, barH, cornerR)
        ctx.fill()

        if (barWidth >= 18 || isHovered) {
          ctx.fillStyle = CHART_COLORS.axis
          ctx.font = VALUE_LABEL_FONT
          ctx.textAlign = 'center'
          ctx.textBaseline = 'bottom'
          ctx.fillText(formatValue(total), xPixel, y - 2)
        }
      })

      // Separator between bars and heatmap
      ctx.strokeStyle = CHART_COLORS.activityDivider
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(0, areaTop - 8)
      ctx.lineTo(areaRight, areaTop - 8)
      ctx.stroke()

      // "Totals" Y-axis label anchored to where Chart.js renders tick labels.
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

  chart = new Chart(canvas.value, {
    type: 'matrix',
    // The highlight outline goes last so it lands on top of the totals bars.
    plugins: [barsPlugin, highlightPlugin],
    data: {
      datasets: [
        {
          data: gridData,
          backgroundColor(ctx) {
            const cell = ctx.dataset.data[ctx.dataIndex]
            if (!cell || cell.v === 0) return CHART_COLORS.heatmapEmptyCell
            const index = Math.min(4, Math.floor((cell.v / rowMaxima[cell.y]) * 5))
            return CHART_COLORS.heatmapPalette[index]
          },
          borderWidth: 0,
          width({ chart }) {
            const a = chart.chartArea
            return a ? Math.max(1, (a.right - a.left) / 24 - 1) : 5
          },
          height({ chart }) {
            const a = chart.chartArea
            return a ? Math.max(1, (a.bottom - a.top) / speciesCount - 1) : 5
          },
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      layout: { padding: { top: PADDING_TOP } },
      plugins: {
        legend: { display: false },
        // The whole hour column is described by the external tooltip driven by
        // the pointer listeners below, so no per-cell tooltip.
        tooltip: { enabled: false },
      },
      scales: {
        x: {
          type: 'linear',
          min: -0.5,
          max: 23.5,
          offset: false,
          grid: { display: false },
          border: { display: false },
          afterBuildTicks: (axis) => {
            axis.ticks = [0, 3, 6, 9, 12, 15, 18, 21].map((value) => ({ value }))
          },
          ticks: {
            font: { size: 12 },
            color: CHART_COLORS.axis,
            callback: (value) => hourLabel(value),
          },
        },
        y: {
          type: 'linear',
          min: -0.5,
          max: speciesCount - 0.5,
          reverse: true,
          offset: false,
          grid: { display: false },
          border: { display: false },
          afterBuildTicks: (axis) => {
            axis.ticks = [...Array(speciesCount).keys()].map((value) => ({ value }))
          },
          ticks: {
            // One label per species, never dropped: without autoSkip:false
            // Chart.js thins Y ticks when rows are short and some species names
            // would be missing.
            autoSkip: false,
            font: { size: 12 },
            color: CHART_COLORS.axis,
            padding: 8,
            callback: (value) => {
              if (value >= 0 && value < speciesCount) {
                return wrapSpeciesLabel(props.species[value].common_name)
              }
              return ''
            },
          },
        },
      },
    },
  })
}

onMounted(() => {
  tooltip = createHourColumnTooltip()
  render()
  canvas.value?.addEventListener('pointermove', handlePointerMove)
  canvas.value?.addEventListener('pointerleave', handlePointerLeave)
  canvas.value?.addEventListener('pointercancel', handlePointerLeave)
})

onUnmounted(() => {
  canvas.value?.removeEventListener('pointermove', handlePointerMove)
  canvas.value?.removeEventListener('pointerleave', handlePointerLeave)
  canvas.value?.removeEventListener('pointercancel', handlePointerLeave)
  chart?.destroy()
  tooltip?.destroy()
})

watch([() => props.species, () => props.days, metric], render, { deep: true })
</script>

<style>
/* Tooltip card built by hourColumnTooltip.js (appended to <body>). */
.hour-tooltip {
  position: fixed;
  pointer-events: none;
  z-index: 9999;
  border: 1px solid;
  border-radius: 2px;
  padding: 8px 10px;
  max-width: calc(100vw - 24px);
  font-family: var(--font-sans);
  opacity: 0;
  transition: opacity 0.12s ease;
}
.hour-tooltip--visible {
  opacity: 1;
}
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
