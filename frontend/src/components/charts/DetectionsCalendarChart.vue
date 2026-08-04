<template>
  <div class="chart-card p-3">
    <div class="chart-label mb-2">
      {{ t('chart.yearlyActivity') }}
    </div>
    <div class="yearly-chart-outer">
      <div class="yearly-chart-wrapper">
        <div
          class="yearly-chart-yaxis"
          :style="{ width: Y_AXIS_WIDTH + 'px', height: chartHeight + 'px' }"
        >
          <span
            v-for="label in yAxisLabels"
            :key="label.row"
            class="yearly-chart-yaxis-label"
            :style="{ top: label.top + 'px' }"
          >
            {{ label.text }}
          </span>
        </div>
        <div ref="scrollContainer" class="yearly-chart-scroll">
          <div
            class="yearly-chart-inner"
            :style="{ width: chartWidth + 'px', height: chartHeight + 'px' }"
          >
            <canvas ref="canvas" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart, LinearScale, Tooltip } from 'chart.js'
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix'
import dayjs from 'dayjs'
import { CHART_COLORS, TOOLTIP_DEFAULTS } from '../../chartColors.js'

const { t } = useI18n()

Chart.register(LinearScale, Tooltip, MatrixController, MatrixElement)

const props = defineProps({
  daily: { type: Object, required: true },
})

const CELL_PITCH = 13
const CELL_GAP = 3
const Y_AXIS_WIDTH = 26
const X_AXIS_HEIGHT = 26
const RIGHT_PADDING = 24

const canvas = ref(null)
const scrollContainer = ref(null)
const chartWidth = ref(0)
const chartHeight = ref(0)
const yAxisLabels = ref([])
let chart = null

function render() {
  if (!canvas.value) return
  if (chart) {
    chart.destroy()
    chart = null
  }

  const today = dayjs()
  const anchor = today.subtract(364, 'day').startOf('week')
  const totalWeeks = today.diff(anchor, 'week') + 1

  chartWidth.value = totalWeeks * CELL_PITCH + RIGHT_PADDING
  chartHeight.value = X_AXIS_HEIGHT + 7 * CELL_PITCH
  yAxisLabels.value = [1, 3, 5].map((row) => ({
    row,
    text: dayjs().startOf('week').add(row, 'day').format('dd'),
    top: row * CELL_PITCH + CELL_PITCH / 2,
  }))

  let max = 1
  Object.values(props.daily).forEach((v) => {
    if (v > max) max = v
  })

  const gridData = []
  const monthTicks = []
  const seenMonths = new Set()

  let current = anchor
  while (!current.isAfter(today)) {
    const dateStr = current.format('YYYY-MM-DD')
    const col = current.diff(anchor, 'week')
    const row = current.diff(current.startOf('week'), 'day')
    gridData.push({ x: col, y: row, v: props.daily[dateStr] ?? 0, date: dateStr })

    const monthKey = current.format('YYYY-MM')
    if (!seenMonths.has(monthKey)) {
      seenMonths.add(monthKey)
      monthTicks.push({ value: col, label: current.format('MMM') })
    }
    current = current.add(1, 'day')
  }

  const monthTickMap = new Map(monthTicks.map(({ value, label }) => [value, label]))

  chart = new Chart(canvas.value, {
    type: 'matrix',
    data: {
      datasets: [
        {
          data: gridData,
          backgroundColor(ctx) {
            const v = ctx.dataset.data[ctx.dataIndex]?.v ?? 0
            if (v === 0) return CHART_COLORS.yearlyEmptyCell
            const ratio = v / max
            return `rgba(${CHART_COLORS.densityRgb},${(0.15 + ratio * 0.85).toFixed(2)})`
          },
          borderWidth: 0,
          width: CELL_PITCH - CELL_GAP,
          height: CELL_PITCH - CELL_GAP,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: { right: RIGHT_PADDING },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...TOOLTIP_DEFAULTS,
          callbacks: {
            title: (items) => {
              const cell = items[0].dataset.data[items[0].dataIndex]
              return dayjs(cell.date).format('ll')
            },
            label: (item) => {
              const cell = item.dataset.data[item.dataIndex]
              return `${cell.v} ${cell.v !== 1 ? t('chart.detections') : t('chart.detection')}`
            },
          },
        },
      },
      scales: {
        x: {
          type: 'linear',
          min: -0.5,
          max: totalWeeks - 0.5,
          offset: false,
          grid: { display: false },
          border: { display: false },
          afterFit: (scale) => {
            scale.height = X_AXIS_HEIGHT
          },
          afterBuildTicks: (axis) => {
            axis.ticks = monthTicks.map(({ value }) => ({ value }))
          },
          ticks: {
            font: { size: 10 },
            color: CHART_COLORS.axis,
            maxRotation: 0,
            callback: (value) => monthTickMap.get(Math.round(value)) ?? '',
          },
        },
        y: {
          type: 'linear',
          min: -0.5,
          max: 6.5,
          reverse: true,
          offset: false,
          grid: { display: false },
          border: { display: false },
          afterFit: (scale) => {
            scale.width = 0
          },
          ticks: { display: false },
        },
      },
    },
  })

  nextTick(() => {
    if (scrollContainer.value) {
      scrollContainer.value.scrollLeft = scrollContainer.value.scrollWidth
    }
  })
}

onMounted(render)
onUnmounted(() => chart?.destroy())
watch(() => props.daily, render)
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

.yearly-chart-inner {
  position: relative;
}
</style>
