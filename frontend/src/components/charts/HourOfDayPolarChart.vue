<template>
  <div class="chart-card p-3 h-100 d-flex flex-column">
    <div class="chart-label mb-2">{{ t('chart.byHourOfDay') }}</div>
    <div class="polar-canvas-wrap">
      <canvas ref="canvas"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Chart, PolarAreaController, ArcElement, RadialLinearScale, Tooltip } from 'chart.js'
import { CHART_COLORS, TOOLTIP_DEFAULTS } from '../../chartColors.js'

const { t } = useI18n()

Chart.register(PolarAreaController, ArcElement, RadialLinearScale, Tooltip)

const props = defineProps({
  hourly: { type: Array, required: true },
})

const canvas = ref(null)
let chart = null

const hourLabels = Array.from({ length: 24 }, (_, i) => {
  const period = i < 12 ? 'AM' : 'PM'
  const hour = i % 12 || 12
  return `${hour}${period}`
})

function render() {
  if (!canvas.value) return
  if (chart) {
    chart.destroy()
    chart = null
  }

  const maxVal = Math.max(...props.hourly, 1)
  chart = new Chart(canvas.value, {
    type: 'polarArea',
    data: {
      labels: hourLabels,
      datasets: [
        {
          data: props.hourly,
          backgroundColor: props.hourly.map(
            (v) => `rgba(${CHART_COLORS.densityRgb},${(0.2 + (v / maxVal) * 0.8).toFixed(2)})`,
          ),
          borderColor: CHART_COLORS.polarBorder,
          borderWidth: 1,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          ...TOOLTIP_DEFAULTS,
          callbacks: {
            label: (item) =>
              `${item.raw} ${item.raw !== 1 ? t('chart.detections') : t('chart.detection')}`,
          },
        },
      },
      scales: {
        r: {
          ticks: { display: false },
          grid: { color: CHART_COLORS.grid },
          pointLabels: { display: true, font: { size: 12 }, color: CHART_COLORS.axis },
        },
      },
    },
  })
}

onMounted(render)
onUnmounted(() => chart?.destroy())
watch(() => props.hourly, render)
</script>

<style scoped>
/* Fill the card so it matches the height of the activity map beside it (desktop). */
.polar-canvas-wrap {
  position: relative;
  flex: 1 1 auto;
  min-height: 260px;
}
</style>
