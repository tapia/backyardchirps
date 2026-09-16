<template>
  <div class="ribbon-card">
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

    <div class="ribbon-body">
      <svg class="ribbon-y-axis" :width="Y_AXIS_WIDTH" :height="SVG_HEIGHT" aria-hidden="true">
        <text
          v-for="tick in yTicks"
          :key="tick.value"
          class="ribbon-axis-label"
          :x="Y_AXIS_WIDTH - 6"
          :y="tick.y"
          text-anchor="end"
          dominant-baseline="middle"
        >
          {{ tick.label }}
        </text>
      </svg>

      <div ref="plotWrapper" class="ribbon-plot-wrapper">
        <svg
          v-if="plotWidth"
          :width="plotWidth"
          :height="SVG_HEIGHT"
          role="img"
          :aria-label="t('page.species.ribbonChart')"
          @click="selectedKey = null"
          @mousemove="trackPointer"
          @mouseleave="hideTooltip"
        >
          <line
            v-for="tick in yTicks.slice(1)"
            :key="tick.value"
            class="ribbon-grid-line"
            x1="0"
            :x2="plotWidth"
            :y1="tick.y"
            :y2="tick.y"
          />
          <g
            v-for="ribbon in ribbons"
            :key="ribbon.key"
            class="ribbon"
            :class="{ 'is-dimmed': activeKey && ribbon.key !== activeKey }"
            :data-species="ribbon.key"
            @click.stop="toggleSpecies(ribbon.key)"
          >
            <path :fill="ribbon.color" :d="ribbon.path" />
            <path class="ribbon-edge" :d="ribbon.edges" />
          </g>
          <g
            v-for="bar in bars"
            :key="bar.key"
            class="ribbon-bar"
            :class="{ 'is-dimmed': activeKey && bar.key !== activeKey }"
            :data-species="bar.key"
            @click.stop="toggleSpecies(bar.key)"
          >
            <path :fill="bar.color" :d="bar.path" />
            <path class="ribbon-edge" :d="bar.edges" />
          </g>
          <line class="ribbon-zero-line" x1="0" :x2="plotWidth" :y1="BASELINE" :y2="BASELINE" />
          <text
            v-for="label in periodNumbers"
            :key="'total-' + label.columnIndex"
            class="ribbon-period-number"
            :x="label.x"
            :y="TOTALS_HEIGHT - 6"
            :text-anchor="label.anchor"
          >
            {{ label.text }}
          </text>
          <text
            v-for="label in xLabels"
            :key="'label-' + label.columnIndex"
            class="ribbon-axis-label"
            :x="label.x"
            :y="BASELINE + 16"
            :text-anchor="label.anchor"
          >
            {{ label.text }}
          </text>
        </svg>

        <div
          v-if="tooltip"
          ref="tooltipCard"
          class="ribbon-tooltip"
          :class="{ 'is-pinned-left': tooltip.pinnedLeft }"
        >
          <div class="species-tooltip__header">
            <div class="species-tooltip__title">{{ tooltip.title }}</div>
            <div class="species-tooltip__summary">{{ tooltip.summary }}</div>
          </div>
          <div v-if="!tooltip.rows.length" class="species-tooltip__empty">
            {{ t('chart.noDetections') }}
          </div>
          <div
            v-else
            class="species-tooltip__rows"
            :class="{ 'species-tooltip__rows--split': tooltip.split }"
          >
            <div
              v-for="row in tooltip.rows"
              :key="row.key"
              class="species-tooltip__row"
              :class="{ 'species-tooltip__row--active': row.active, 'is-silent': row.silent }"
            >
              <span class="species-tooltip__name">{{ row.name }}</span>
              <span class="species-tooltip__count">{{ row.count }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { CHART_COLORS } from '../../chartColors.js'
import { formatTimelineLabel, timelineLabelIndexes } from './chartLabels.js'
import { HEADER_FONT } from './chartStyle.js'

// Height of the area the stacks can grow into, and of the bands above and below it.
const PLOT_HEIGHT = 280
const TOTALS_HEIGHT = 20
const X_AXIS_HEIGHT = 24
const SVG_HEIGHT = TOTALS_HEIGHT + PLOT_HEIGHT + X_AXIS_HEIGHT
const BASELINE = TOTALS_HEIGHT + PLOT_HEIGHT
const Y_AXIS_WIDTH = 40

// Space between two species in a stack, and the height a bar gets on top of its count, so a
// species heard once stays visibly thicker than one not heard at all.
const GAP = 2
const FLOOR = 1.5

// With 0, every column fits in the card however many there are. Raise it (to 28, say) and a
// long period scrolls sideways instead, with the y axis staying in place.
const MIN_COLUMN_WIDTH = 0

// Columns narrower than this show the number above them only where the x axis has a label,
// since every number would overlap its neighbours.
const MIN_WIDTH_FOR_EVERY_NUMBER = 24

// A label whose centre is closer than this to either edge is aligned to its column instead
// of centred on it, so it is not cut off.
const LABEL_EDGE = 30

// About how many steps the y axis is split into.
const Y_TICK_TARGET = 4

// Above this many species the tooltip list splits into two columns, and the tooltip moves
// to the left edge when the pointer gets this close to it.
const TWO_COLUMN_THRESHOLD = 14
const TOOLTIP_CLEARANCE = 10

const { t } = useI18n()

const props = defineProps({
  series: { type: Array, required: true },
  granularity: { type: String, required: true },
})

const selectedKey = ref(null)
const tooltip = ref(null)
const tooltipCard = ref(null)
const plotWrapper = ref(null)
const availableWidth = ref(0)
let resizeObserver = null

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

// For each column, the top and bottom of every species' bar, indexed like speciesRows.
const stacks = computed(() =>
  columns.value.map((day, columnIndex) => stackColumn(speciesRows.value, columnIndex, scale.value)),
)

const plotWidth = computed(() =>
  Math.max(availableWidth.value, columns.value.length * MIN_COLUMN_WIDTH),
)

const columnWidth = computed(() => plotWidth.value / Math.max(1, columns.value.length))

const barWidth = computed(() => Math.max(3, Math.min(3, columnWidth.value * 0.08)))

const columnCenters = computed(() =>
  columns.value.map((day, columnIndex) => columnWidth.value * (columnIndex + 0.5)),
)

// The ribbons of the selected species are painted last so they cross over all the others.
// Otherwise the species heard most are painted on top.
const ribbons = computed(() => {
  const halfBar = barWidth.value / 2
  const centers = columnCenters.value
  const rows = speciesRows.value.map((row, rowIndex) => {
    const segments = []
    for (let columnIndex = 0; columnIndex < centers.length - 1; columnIndex++) {
      segments.push(
        ribbonSegment(
          centers[columnIndex] + halfBar,
          centers[columnIndex + 1] - halfBar,
          stacks.value[columnIndex][rowIndex],
          stacks.value[columnIndex + 1][rowIndex],
        ),
      )
    }
    return {
      key: row.key,
      color: row.color,
      total: row.total,
      path: segments.map((segment) => segment.fill).join(' '),
      edges: segments.map((segment) => segment.edges).join(' '),
    }
  })
  return rows.sort(
    (first, second) =>
      (first.key === activeKey.value) - (second.key === activeKey.value) ||
      first.total - second.total,
  )
})

// A bar carries the same outline as the ribbons that meet it, on its top and bottom edges
// only. Without it the bar would show half a pixel more colour than the ribbon beside it,
// which reads as a small spike at every column.
const bars = computed(() => {
  const halfBar = barWidth.value / 2
  return speciesRows.value.map((row, rowIndex) => {
    const fills = []
    const edges = []
    columnCenters.value.forEach((center, columnIndex) => {
      const { top, bottom } = stacks.value[columnIndex][rowIndex]
      if (top === bottom) return
      const [left, right] = [round(center - halfBar), round(center + halfBar)]
      const [barTop, barBottom] = [round(top), round(bottom)]
      fills.push(`M${left},${barTop}H${right}V${barBottom}H${left}Z`)
      edges.push(`M${left},${barTop}H${right} M${left},${barBottom}H${right}`)
    })
    return { key: row.key, color: row.color, path: fills.join(''), edges: edges.join(' ') }
  })
})

const labelIndexes = computed(() => timelineLabelIndexes(columns.value.length, props.granularity))

const xLabels = computed(() =>
  labelIndexes.value.map((columnIndex) => ({
    columnIndex,
    text: formatTimelineLabel(columns.value[columnIndex], props.granularity),
    ...labelPosition(columnIndex),
  })),
)

// The period totals, or the selected species' own count in each period.
const periodNumbers = computed(() => {
  const selectedRow = speciesRows.value.find((row) => row.key === activeKey.value)
  const counts = selectedRow ? selectedRow.counts : periodTotals.value
  const indexes =
    columnWidth.value >= MIN_WIDTH_FOR_EVERY_NUMBER
      ? counts.map((count, index) => index)
      : labelIndexes.value
  return indexes.map((columnIndex) => ({
    columnIndex,
    text: counts[columnIndex].toLocaleString(),
    ...labelPosition(columnIndex),
  }))
})

const yTicks = computed(() => {
  if (!scale.value) return [{ value: 0, y: BASELINE, label: '0' }]
  const step = niceStep(maxTotal.value / Y_TICK_TARGET)
  const ticks = []
  for (let value = 0; value * scale.value <= PLOT_HEIGHT; value += step) {
    ticks.push({ value, y: BASELINE - value * scale.value, label: value.toLocaleString() })
  }
  return ticks
})

function toggleSpecies(key) {
  selectedKey.value = activeKey.value === key ? null : key
}

/*
 * The card for the period under the pointer, listing every species of the chart. Rows
 * follow the legend, so a name sits in the same place whichever period is hovered, and
 * the species the pointer is on is marked.
 */
function trackPointer(event) {
  const plotRect = plotWrapper.value.getBoundingClientRect()
  const pointerX = event.clientX - plotRect.left + plotWrapper.value.scrollLeft
  const columnIndex = columnAt(pointerX)
  const hoveredKey = event.target.closest('[data-species]')?.dataset.species ?? null
  const cardWidth = tooltipCard.value?.offsetWidth ?? 0
  tooltip.value = {
    // The card rests on the right, and moves to the left edge once the pointer reaches it.
    pinnedLeft: pointerX > plotWidth.value - cardWidth - TOOLTIP_CLEARANCE,
    title: formatTimelineLabel(columns.value[columnIndex], props.granularity),
    summary: `${t('chart.totalDetections')}: ${periodTotals.value[columnIndex]}`,
    split: legendRows.value.length > TWO_COLUMN_THRESHOLD,
    rows: periodTotals.value[columnIndex]
      ? legendRows.value.map((row) => tooltipRow(row, columnIndex, hoveredKey))
      : [],
  }
}

function hideTooltip() {
  tooltip.value = null
}

function columnAt(x) {
  const columnIndex = Math.floor(x / columnWidth.value)
  return Math.min(Math.max(columnIndex, 0), columns.value.length - 1)
}

function tooltipRow(row, columnIndex, hoveredKey) {
  const count = row.counts[columnIndex]
  const unit = count !== 1 ? t('chart.detections') : t('chart.detection')
  return {
    key: row.key,
    name: row.name,
    count: `${count} ${unit}`,
    active: row.key === hoveredKey,
    silent: count === 0,
  }
}

function labelPosition(columnIndex) {
  const center = columnCenters.value[columnIndex]
  const halfBar = barWidth.value / 2
  if (center < LABEL_EDGE) return { x: center - halfBar, anchor: 'start' }
  if (center > plotWidth.value - LABEL_EDGE) return { x: center + halfBar, anchor: 'end' }
  return { x: center, anchor: 'middle' }
}

onMounted(() => {
  resizeObserver = new ResizeObserver(([entry]) => {
    availableWidth.value = Math.floor(entry.contentRect.width)
  })
  resizeObserver.observe(plotWrapper.value)
})
onUnmounted(() => resizeObserver?.disconnect())

// One column as a stack rising from the baseline, the species heard most on top and ties
// going to the larger total. A species not heard in the period collapses to a point on the
// baseline, which is where its ribbons taper to.
function stackColumn(rows, columnIndex, pixelsPerDetection) {
  const bottomToTop = rows
    .map((row, rowIndex) => rowIndex)
    .sort(
      (first, second) =>
        rows[first].counts[columnIndex] - rows[second].counts[columnIndex] ||
        rows[first].total - rows[second].total ||
        second - first,
    )
  const extents = new Array(rows.length)
  let cursor = BASELINE
  let stackedCount = 0
  for (const rowIndex of bottomToTop) {
    const count = rows[rowIndex].counts[columnIndex]
    if (!count) {
      extents[rowIndex] = { top: BASELINE, bottom: BASELINE }
      continue
    }
    if (stackedCount) cursor -= GAP
    const top = cursor - (count * pixelsPerDetection + FLOOR)
    extents[rowIndex] = { top, bottom: cursor }
    cursor = top
    stackedCount++
  }
  return extents
}

// The band carrying one species from its bar in one column to its bar in the next. Both
// control points of each edge sit at the horizontal midpoint, so the band leaves and meets
// each bar flat and crosses the others in an S. The outline that separates it from the ribbons
// it crosses follows only the two curves: on the straight ends it would draw a line at every
// column.
function ribbonSegment(fromX, toX, from, to) {
  const middle = round((fromX + toX) / 2)
  const [x0, x1] = [round(fromX), round(toX)]
  const [fromTop, fromBottom, toTop, toBottom] = [from.top, from.bottom, to.top, to.bottom].map(
    round,
  )
  const topCurve = `C${middle},${fromTop} ${middle},${toTop} ${x1},${toTop}`
  const bottomCurve = `C${middle},${toBottom} ${middle},${fromBottom} ${x0},${fromBottom}`
  return {
    fill: `M${x0},${fromTop} ${topCurve} L${x1},${toBottom} ${bottomCurve} Z`,
    edges: `M${x0},${fromTop} ${topCurve} M${x1},${toBottom} ${bottomCurve}`,
  }
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

function round(value) {
  return Math.round(value * 100) / 100
}
</script>

<style scoped>
.ribbon-card {
  position: relative;
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
  margin-bottom: 14px;
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

.ribbon-body {
  display: flex;
}

.ribbon-y-axis {
  flex: none;
  display: block;
}

.ribbon-plot-wrapper {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  overflow-x: auto;
}

.ribbon-plot-wrapper svg {
  display: block;
}

.ribbon-axis-label {
  font-size: 11px;
  fill: var(--ribbon-muted);
}

.ribbon-period-number {
  font-size: 11px;
  font-weight: 500;
  fill: var(--ribbon-ink);
}

.ribbon-grid-line {
  stroke: var(--ribbon-grid);
  stroke-width: 1;
}

.ribbon-zero-line {
  stroke: var(--ribbon-ink);
  stroke-width: 1;
}

.ribbon {
  cursor: pointer;
  transition: opacity 0.15s;
}

.ribbon-edge {
  fill: none;
  stroke: var(--ribbon-paper);
  stroke-width: 1;
}

.ribbon.is-dimmed {
  opacity: 0.07;
}

.ribbon-bar {
  cursor: pointer;
  transition: opacity 0.15s;
}

.ribbon-bar.is-dimmed {
  opacity: 0.15;
}

/*
 * The card the ECharts tooltips draw, rebuilt here: this chart has no library to draw it.
 * Its contents use the shared .species-tooltip__ classes from style.css, which carry the
 * layout but leave the colours to whoever draws the card.
 */
.ribbon-tooltip {
  position: absolute;
  top: v-bind('TOTALS_HEIGHT + "px"');
  right: 0;
  z-index: 2;
  max-width: 100%;
  padding: 8px 10px;
  border: 1px solid v-bind('CHART_COLORS.tooltip.border');
  border-radius: 2px;
  background-color: v-bind('CHART_COLORS.tooltip.background');
  color: v-bind('CHART_COLORS.tooltip.body');
  font-family: v-bind('HEADER_FONT');
  pointer-events: none;
}

.ribbon-tooltip.is-pinned-left {
  right: auto;
  left: 0;
}

.ribbon-tooltip .species-tooltip__title,
.ribbon-tooltip .species-tooltip__count {
  color: v-bind('CHART_COLORS.tooltip.title');
}

/* A species not heard in the period stays on the list, in the axis grey. */
.ribbon-tooltip .is-silent .species-tooltip__name,
.ribbon-tooltip .is-silent .species-tooltip__count {
  color: v-bind('CHART_COLORS.axis');
}
</style>
