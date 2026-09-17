<template>
  <div ref="card" class="ribbon-card">
    <VChart
      ref="chart"
      :option="option"
      :style="{ height: CHART_HEIGHT + 'px' }"
      role="img"
      :aria-label="t('page.species.ribbonChart')"
      autoresize
      @click="toggleClickedSpecies"
      @zr:click="clearSelectionOnBackground"
      @mouseover="markHoveredSpecies"
      @mouseout="unmarkHoveredSpecies"
    />

    <div class="ribbon-legend">
      <button
        v-for="row in legendRows"
        :key="row.key"
        type="button"
        class="ribbon-chip"
        :class="{
          'is-light': row.isLight,
          'is-selected': row.key === activeKey,
          'is-dimmed': activeKey && row.key !== activeKey,
        }"
        :style="{ backgroundColor: row.color }"
        :aria-pressed="row.key === activeKey"
        @click="toggleSpecies(row.key)"
      >
        {{ row.name }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { use } from 'echarts/core'
import { CustomChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { CHART_COLORS } from '../../chartColors.js'
import { formatTimelineLabel, timelineLabelStep } from './chartLabels.js'
import { RIBBON_FONT } from './chartStyle.js'
import { SPECIES_TOOLTIP, speciesTooltipHtml } from './speciesTooltip.js'

use([CanvasRenderer, CustomChart, GridComponent, LineChart, TooltipComponent])

// Height of the area the stacks can grow into, and of the bands above and below it. The top
// band only keeps the label of the highest y axis tick from being cut in half.
const PLOT_HEIGHT = 480
const TOP_MARGIN = 8
const X_AXIS_HEIGHT = 24
const CHART_HEIGHT = TOP_MARGIN + PLOT_HEIGHT + X_AXIS_HEIGHT
const Y_AXIS_WIDTH = 40

// Space between two species in a stack, and the height a bar gets on top of its count, so a
// species heard once stays visibly thicker than one not heard at all. Both in pixels.
const GAP = 2
const FLOOR = 1.5

// Width of the bar every species has at each column, where its ribbons start and end.
const BAR_WIDTH = 3

// About how many steps the y axis is split into.
const Y_TICK_TARGET = 4

// While a species is selected the others fade: their ribbons almost disappear, and their bars
// stay visible enough to show where each column is.
const DIMMED_RIBBON_OPACITY = 0.07
const DIMMED_BAR_OPACITY = 0.15

// Space kept free between two x axis labels.
const LABEL_GAP = 12

// The tooltip moves to the left edge when the pointer gets this close to it.
const TOOLTIP_CLEARANCE = 10

const AXIS_TEXT = { color: CHART_COLORS.ribbon.muted, fontSize: 11, fontFamily: RIBBON_FONT }

const { t } = useI18n()

const props = defineProps({
  series: { type: Array, required: true },
  granularity: { type: String, required: true },
})

const card = ref(null)
const chart = ref(null)
const selectedKey = ref(null)
const plotWidth = ref(0)
let resizeObserver = null

// The species under the pointer, for the tooltip. Not reactive: the chart does not change
// when it does, only the tooltip does, and that is refreshed by hand.
let hoveredKey = null

// Every period any species has, in time order. The series normally share the same periods,
// but over all time each one lists only the months it was heard in.
const columns = computed(() =>
  [...new Set(props.series.flatMap((entry) => entry.data.map((point) => point.day)))].sort(),
)

const speciesRows = computed(() =>
  props.series.map((entry, seriesIndex) => {
    const countsByDay = new Map(entry.data.map((point) => [point.day, point.count]))
    const counts = columns.value.map((day) => countsByDay.get(day) ?? 0)
    const palette = CHART_COLORS.ribbonPalette
    const color = palette[seriesIndex % palette.length]
    return {
      key: entry.scientific_name,
      name: entry.common_name,
      color,
      isLight: isLightColor(color),
      counts,
      total: counts.reduce((sum, count) => sum + count, 0),
    }
  }),
)

const legendRows = computed(() =>
  [...speciesRows.value].sort((first, second) => second.total - first.total),
)

// A selection survives a period change only while its species is still in the chart.
const activeKey = computed(() =>
  speciesRows.value.some((row) => row.key === selectedKey.value) ? selectedKey.value : null,
)

const periodTotals = computed(() =>
  columns.value.map((day, columnIndex) =>
    speciesRows.value.reduce((sum, row) => sum + row.counts[columnIndex], 0),
  ),
)

const maxTotal = computed(() => Math.max(0, ...periodTotals.value))

// Pixels per detection, chosen so the tallest stack, with its floors and gaps, fills the plot.
const scale = computed(() => {
  if (!maxTotal.value) return 0
  const speciesCount = speciesRows.value.length
  return (PLOT_HEIGHT - (speciesCount - 1) * GAP - speciesCount * FLOOR) / maxTotal.value
})

// For each species, the bottom and top of its bar in every column, in detections, with the
// floors and gaps converted to detections too so the y axis can place them.
const extents = computed(() => {
  const byColumn = columns.value.map((day, columnIndex) =>
    stackColumn(speciesRows.value, columnIndex, scale.value),
  )
  return speciesRows.value.map((row, rowIndex) => byColumn.map((column) => column[rowIndex]))
})

const xLabels = computed(() =>
  columns.value.map((day) => formatTimelineLabel(day, props.granularity)),
)

// Every how many columns the x axis has a label: the usual spacing, or wider when the labels
// would not fit side by side. Labels count back from the last column, whose label is aligned
// to the right edge so it is not cut off. That label reaches a whole label width to the left
// of its column instead of half, and the spacing leaves room for it.
const labelStep = computed(() => {
  const usualStep = timelineLabelStep(columns.value.length, props.granularity)
  if (!plotWidth.value || !columns.value.length) return usualStep
  const columnWidth = plotWidth.value / columns.value.length
  const labelWidth = widestLabelWidth(xLabels.value)
  const neededStep = Math.ceil((1.5 * labelWidth + LABEL_GAP) / columnWidth)
  return Math.max(usualStep, neededStep)
})

const option = computed(() => {
  const lastColumn = columns.value.length - 1
  const step = labelStep.value
  const rows = speciesRows.value

  // The ribbons of the selected species are painted last so they cross over all the others.
  // Otherwise the species heard most are painted on top.
  const paintOrder = rows
    .map((row, rowIndex) => rowIndex)
    .sort(
      (first, second) =>
        (rows[first].key === activeKey.value) - (rows[second].key === activeKey.value) ||
        rows[first].total - rows[second].total,
    )

  return {
    animation: false,
    grid: {
      top: TOP_MARGIN,
      bottom: X_AXIS_HEIGHT,
      left: Y_AXIS_WIDTH,
      right: 0,
      outerBoundsMode: 'none',
    },
    xAxis: {
      type: 'category',
      data: xLabels.value,
      axisLine: { lineStyle: { color: CHART_COLORS.ribbon.ink } },
      axisTick: { show: false },
      axisLabel: {
        ...AXIS_TEXT,
        margin: 6,
        interval: (columnIndex) => (lastColumn - columnIndex) % step === 0,
        alignMinLabel: 'left',
        alignMaxLabel: 'right',
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      // The value at the top of the plot, so the tallest stack reaches it exactly.
      max: scale.value ? PLOT_HEIGHT / scale.value : 1,
      interval: niceStep(maxTotal.value / Y_TICK_TARGET),
      axisLine: { show: false },
      axisTick: { show: false },
      // The top of the plot is not a round number, so it gets no label and no line.
      axisLabel: {
        ...AXIS_TEXT,
        margin: 6,
        showMaxLabel: false,
        formatter: (value) => value.toLocaleString(),
      },
      splitLine: {
        lineStyle: { color: CHART_COLORS.ribbon.grid },
        showMinLine: false,
        showMaxLine: false,
      },
    },
    tooltip: {
      ...SPECIES_TOOLTIP,
      trigger: 'axis',
      axisPointer: { type: 'none' },
      position: tooltipPosition,
      formatter: tooltipHtml,
    },
    series: [
      // Never drawn. It gives the axis tooltip a value in every column, whatever the pointer
      // is over.
      {
        type: 'line',
        data: periodTotals.value,
        symbol: 'none',
        lineStyle: { opacity: 0 },
        silent: true,
      },
      {
        type: 'custom',
        data: paintOrder.map((rowIndex) => [rowIndex]),
        emphasis: { disabled: true },
        renderItem: (params, api) => ribbonShape(api, api.value(0)),
      },
      {
        type: 'custom',
        data: rows.map((row, rowIndex) => [rowIndex]),
        emphasis: { disabled: true },
        renderItem: (params, api) => barShape(api, api.value(0)),
      },
    ],
  }
})

onMounted(() => {
  resizeObserver = new ResizeObserver(([entry]) => {
    plotWidth.value = Math.floor(entry.contentRect.width) - Y_AXIS_WIDTH
  })
  resizeObserver.observe(card.value)
})
onUnmounted(() => resizeObserver?.disconnect())

function toggleSpecies(key) {
  selectedKey.value = activeKey.value === key ? null : key
}

function toggleClickedSpecies(params) {
  if (params.seriesType !== 'custom') return
  toggleSpecies(speciesRows.value[params.value[0]].key)
}

// A click on the empty plot, away from every ribbon and bar, clears the selection.
function clearSelectionOnBackground(event) {
  if (!event.target) selectedKey.value = null
}

function markHoveredSpecies(params) {
  if (params.seriesType !== 'custom') return
  hoveredKey = speciesRows.value[params.value[0]].key
  refreshTooltip(params.event)
}

function unmarkHoveredSpecies(params) {
  if (params.seriesType !== 'custom') return
  hoveredKey = null
  refreshTooltip(params.event)
}

// An axis tooltip is only rebuilt when the pointer moves to another column. Hiding it first
// makes ECharts build it again, so the marked row follows the pointer within a column too.
function refreshTooltip(event) {
  chart.value.dispatchAction({ type: 'hideTip' })
  chart.value.dispatchAction({ type: 'showTip', x: event.offsetX, y: event.offsetY })
}

/*
 * The card for the period under the pointer, listing every species of the chart. Rows
 * follow the legend, so a name sits in the same place whichever period is hovered, and the
 * species the pointer is on is marked.
 */
function tooltipHtml(params) {
  const columnIndex = params.find((entry) => entry.seriesType === 'line')?.dataIndex
  if (columnIndex === undefined) return ''
  const total = periodTotals.value[columnIndex]
  return speciesTooltipHtml({
    title: formatTimelineLabel(columns.value[columnIndex], props.granularity),
    summary: `${t('chart.totalDetections')}: ${total}`,
    rows: total ? legendRows.value.map((row) => tooltipRow(row, columnIndex)) : [],
    emptyText: t('chart.noDetections'),
  })
}

function tooltipRow(row, columnIndex) {
  const count = row.counts[columnIndex]
  const unit = count !== 1 ? t('chart.detections') : t('chart.detection')
  return {
    name: row.name,
    count: `${count} ${unit}`,
    active: row.key === hoveredKey,
    silent: count === 0,
  }
}

/*
 * Pinned to the top of the plot instead of following the pointer, so the card holds still
 * while you move across the periods. It rests on the right and moves to the left edge once
 * the pointer would end up underneath it.
 */
function tooltipPosition(point, params, element, rect, size) {
  const [chartWidth] = size.viewSize
  const pinnedRight = chartWidth - size.contentSize[0]
  const clearsPointer = point[0] < pinnedRight - TOOLTIP_CLEARANCE
  return [clearsPointer ? pinnedRight : Y_AXIS_WIDTH, TOP_MARGIN]
}

// One species' ribbons, from its bar in each column to its bar in the next.
function ribbonShape(api, rowIndex) {
  const row = speciesRows.value[rowIndex]
  const rowExtents = extents.value[rowIndex]
  if (rowExtents.length < 2) return null
  const opacity = activeKey.value && row.key !== activeKey.value ? DIMMED_RIBBON_OPACITY : 1
  const segments = rowExtents
    .slice(0, -1)
    .map((extent, columnIndex) =>
      ribbonSegment(
        pixelExtent(api, columnIndex, extent),
        pixelExtent(api, columnIndex + 1, rowExtents[columnIndex + 1]),
      ),
    )
  return outlinedShape(
    row.color,
    opacity,
    segments.map((segment) => segment.fill).join(' '),
    segments.map((segment) => segment.edges).join(' '),
  )
}

// One species' bars, one per column it was heard in.
function barShape(api, rowIndex) {
  const row = speciesRows.value[rowIndex]
  const rowExtents = extents.value[rowIndex]
  const opacity = activeKey.value && row.key !== activeKey.value ? DIMMED_BAR_OPACITY : 1
  const fills = []
  const edges = []
  rowExtents.forEach((extent, columnIndex) => {
    if (extent.top === extent.bottom) return
    const { x, top, bottom } = pixelExtent(api, columnIndex, extent)
    const [left, right] = [x - BAR_WIDTH / 2, x + BAR_WIDTH / 2]
    fills.push(`M${left},${top}H${right}V${bottom}H${left}Z`)
    edges.push(`M${left},${top}H${right} M${left},${bottom}H${right}`)
  })
  if (!fills.length) return null
  return outlinedShape(row.color, opacity, fills.join(''), edges.join(' '))
}

// A column's bar in pixels: its centre, top and bottom.
function pixelExtent(api, columnIndex, extent) {
  const [x, top] = api.coord([columnIndex, extent.top])
  const [, bottom] = api.coord([columnIndex, extent.bottom])
  return { x, top, bottom }
}

/*
 * A filled shape with an outline in the card's colour, which separates one species from the
 * next. The outline is given its own path so it can leave out the straight ends of the
 * ribbons and the sides of the bars: drawn there, it would make a light line at every column.
 * The bars carry it on their top and bottom, or they would show half a pixel more colour than
 * the ribbons meeting them, which reads as a small spike.
 */
function outlinedShape(color, opacity, fillPath, edgePath) {
  return {
    type: 'group',
    children: [
      { type: 'path', shape: { pathData: fillPath }, style: { fill: color, opacity } },
      {
        type: 'path',
        shape: { pathData: edgePath },
        style: { fill: 'none', stroke: CHART_COLORS.ribbon.paper, lineWidth: 1, opacity },
      },
    ],
  }
}

// One column as a stack rising from zero, the species heard most on top and ties going to the
// larger total. A species not heard in the period collapses to a point at zero, which is where
// its ribbons taper to.
function stackColumn(rows, columnIndex, pixelsPerDetection) {
  const extentsByRow = new Array(rows.length)
  if (!pixelsPerDetection) return extentsByRow.fill({ bottom: 0, top: 0 })
  const bottomToTop = rows
    .map((row, rowIndex) => rowIndex)
    .sort(
      (first, second) =>
        rows[first].counts[columnIndex] - rows[second].counts[columnIndex] ||
        rows[first].total - rows[second].total ||
        second - first,
    )
  let cursor = 0
  let stackedCount = 0
  for (const rowIndex of bottomToTop) {
    const count = rows[rowIndex].counts[columnIndex]
    if (!count) {
      extentsByRow[rowIndex] = { bottom: 0, top: 0 }
      continue
    }
    if (stackedCount) cursor += GAP / pixelsPerDetection
    const top = cursor + count + FLOOR / pixelsPerDetection
    extentsByRow[rowIndex] = { bottom: cursor, top }
    cursor = top
    stackedCount++
  }
  return extentsByRow
}

// The band carrying one species from its bar in one column to its bar in the next. Both
// control points of each edge sit at the horizontal midpoint, so the band leaves and meets
// each bar flat and crosses the others in an S. The edges path holds only the two curves.
function ribbonSegment(from, to) {
  const [x0, x1] = [from.x + BAR_WIDTH / 2, to.x - BAR_WIDTH / 2]
  const middle = (x0 + x1) / 2
  const topCurve = `C${middle},${from.top} ${middle},${to.top} ${x1},${to.top}`
  const bottomCurve = `C${middle},${to.bottom} ${middle},${from.bottom} ${x0},${from.bottom}`
  return {
    fill: `M${x0},${from.top} ${topCurve} L${x1},${to.bottom} ${bottomCurve} Z`,
    edges: `M${x0},${from.top} ${topCurve} M${x1},${to.bottom} ${bottomCurve}`,
  }
}

// How wide the longest x axis label is drawn, in pixels.
function widestLabelWidth(labels) {
  const context = document.createElement('canvas').getContext('2d')
  context.font = `${AXIS_TEXT.fontSize}px ${RIBBON_FONT}`
  return Math.max(0, ...labels.map((label) => context.measureText(label).width))
}

// A round step for the y axis: 1, 2 or 5 times a power of ten, and never below one detection.
function niceStep(roughStep) {
  if (roughStep <= 1) return 1
  const magnitude = 10 ** Math.floor(Math.log10(roughStep))
  const residual = roughStep / magnitude
  const factor = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10
  return factor * magnitude
}

// Whether dark text reads better than white on a colour. 0.179 is the relative luminance at
// which both have the same contrast.
function isLightColor(hex) {
  const [red, green, blue] = [1, 3, 5].map((offset) => {
    const channel = parseInt(hex.slice(offset, offset + 2), 16) / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue > 0.179
}
</script>

<style scoped>
.ribbon-card {
  background-color: var(--ribbon-paper);
  color: var(--ribbon-ink);
  font-family: var(--font-grotesk);
  border-radius: 12px;
  padding: 18px;
}

.ribbon-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}

.ribbon-chip {
  border: none;
  border-radius: 999px;
  padding: 3px 11px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
  color: #fff;
  transition: opacity 0.15s;
}

.ribbon-chip.is-light {
  color: var(--ribbon-ink);
}

.ribbon-chip.is-selected {
  box-shadow:
    0 0 0 2px var(--ribbon-paper),
    0 0 0 3px var(--ribbon-ink);
}

.ribbon-chip.is-dimmed {
  opacity: 0.35;
}
</style>
