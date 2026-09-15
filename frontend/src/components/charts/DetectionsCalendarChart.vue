<template>
  <div class="chart-card p-3">
    <div class="chart-label mb-2">
      {{ t('chart.yearlyActivity') }}
    </div>
    <div class="yearly-chart-outer">
      <div class="yearly-chart-wrapper">
        <!-- Outside the scrolling area, so the day names stay put while it scrolls. -->
        <div
          class="yearly-chart-yaxis"
          :style="{ width: Y_AXIS_WIDTH + 'px', height: chartHeight + 'px' }"
        >
          <span
            v-for="label in dayLabels"
            :key="label.row"
            class="yearly-chart-yaxis-label"
            :style="{ top: label.top + 'px' }"
          >
            {{ label.text }}
          </span>
        </div>
        <div ref="scrollContainer" class="yearly-chart-scroll">
          <VChart
            :option="option"
            :style="{ width: chartWidth + 'px', height: chartHeight + 'px' }"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { use, format } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import {
  CalendarComponent,
  TooltipComponent,
  VisualMapContinuousComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import { CHART_COLORS } from '../../chartColors.js'

use([
  CalendarComponent,
  CanvasRenderer,
  HeatmapChart,
  TooltipComponent,
  VisualMapContinuousComponent,
])

const { t } = useI18n()

const props = defineProps({
  // { 'YYYY-MM-DD': count }
  daily: { type: Object, required: true },
})

// Canvas text cannot read CSS custom properties, so the font stack is written out.
const AXIS_FONT = "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif"

// Each day is a 10px square with a 3px gap, drawn as a 13px cell outlined in the card colour.
const CELL_PITCH = 13
const CELL_GAP = 3
const Y_AXIS_WIDTH = 26
const X_AXIS_HEIGHT = 26
// Room for the last month's label, which starts at its first week.
const RIGHT_PADDING = 24
const MONTH_LABEL_GAP = 8
// Rows that get a day name, counted from the first day of the week.
const LABELLED_ROWS = [1, 3, 5]
// The colour scale starts at this opacity, so a day with one detection still shows.
const MIN_OPACITY = 0.15
const NO_DETECTIONS = -1

const scrollContainer = ref(null)

const today = computed(() => dayjs())
// A full year back, starting at the beginning of that week.
const firstDay = computed(() => today.value.subtract(364, 'day').startOf('week'))
const weekCount = computed(() => today.value.diff(firstDay.value, 'week') + 1)

const chartWidth = computed(() => weekCount.value * CELL_PITCH + RIGHT_PADDING)
const chartHeight = 7 * CELL_PITCH + X_AXIS_HEIGHT

const dayLabels = computed(() =>
  LABELLED_ROWS.map((row) => ({
    row,
    text: firstDay.value.add(row, 'day').format('dd'),
    top: row * CELL_PITCH + CELL_PITCH / 2,
  })),
)

const option = computed(() => {
  const days = []
  for (let day = firstDay.value; !day.isAfter(today.value); day = day.add(1, 'day')) {
    days.push(day.format('YYYY-MM-DD'))
  }
  const maximum = Math.max(1, ...Object.values(props.daily))

  return {
    animation: false,
    calendar: {
      range: [days[0], days[days.length - 1]],
      orient: 'horizontal',
      left: 0,
      top: 0,
      cellSize: CELL_PITCH,
      firstDay: firstDay.value.day(),
      splitLine: { show: false },
      itemStyle: { color: 'transparent', borderWidth: 0 },
      dayLabel: { show: false },
      yearLabel: { show: false },
      monthLabel: {
        position: 'end',
        align: 'left',
        margin: MONTH_LABEL_GAP,
        color: CHART_COLORS.axis,
        fontSize: 10,
        fontFamily: AXIS_FONT,
        nameMap: Array.from({ length: 12 }, (unused, month) => dayjs().month(month).format('MMM')),
      },
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
    /*
     * Busier days are more opaque, from MIN_OPACITY up to full strength at the
     * busiest. Days without detections carry NO_DETECTIONS, below the range, and
     * get the empty-cell colour instead.
     */
    visualMap: {
      show: false,
      type: 'continuous',
      dimension: 2,
      min: 0,
      max: maximum,
      inRange: {
        color: [
          `rgba(${CHART_COLORS.densityRgb}, ${MIN_OPACITY})`,
          `rgba(${CHART_COLORS.densityRgb}, 1)`,
        ],
      },
      outOfRange: { color: CHART_COLORS.yearlyEmptyCell },
    },
    series: {
      type: 'heatmap',
      coordinateSystem: 'calendar',
      itemStyle: { borderColor: CHART_COLORS.heatmapCellGap, borderWidth: CELL_GAP },
      emphasis: { disabled: true },
      // [day, count, colour value]
      data: days.map((day) => {
        const count = props.daily[day] ?? 0
        return [day, count, count > 0 ? count : NO_DETECTIONS]
      }),
    },
  }
})

function tooltipHtml(params) {
  const [day, count] = params.value
  const unit = count !== 1 ? t('chart.detections') : t('chart.detection')
  return (
    `<div class="chart-tooltip-title" style="color: ${CHART_COLORS.tooltip.title}">` +
    `${format.encodeHTML(dayjs(day).format('ll'))}</div>` +
    `<span class="chart-tooltip-swatch" style="background: ${params.color}"></span>` +
    format.encodeHTML(`${count} ${unit}`)
  )
}

// On a narrow screen the year does not fit; open it at the most recent weeks.
function scrollToToday() {
  nextTick(() => {
    if (scrollContainer.value) scrollContainer.value.scrollLeft = scrollContainer.value.scrollWidth
  })
}

onMounted(scrollToToday)
watch(() => props.daily, scrollToToday)
</script>

<style scoped>
.yearly-chart-outer {
  display: flex;
  justify-content: center;
}

.yearly-chart-wrapper {
  display: flex;
  max-width: 100%;
}

.yearly-chart-yaxis {
  position: relative;
  flex: 0 0 auto;
}

.yearly-chart-yaxis-label {
  position: absolute;
  right: 4px;
  transform: translateY(-50%);
  font-size: 10px;
  white-space: nowrap;
  color: v-bind('CHART_COLORS.axis');
}

.yearly-chart-scroll {
  overflow-x: auto;
  overflow-y: hidden;
}
</style>
