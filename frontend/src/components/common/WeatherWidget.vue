<template>
  <div v-if="weather" class="weather-widget" :class="{ 'weather-widget-compact': compact }">
    <!-- Compact: a small icon + temperature chip. Everything else (date/time,
         feels-like, wind) is revealed on hover through a popover-style tooltip.
         Used in the desktop navbar, where horizontal space is tight. -->
    <div
      v-if="compact"
      class="weather-chip"
      v-bs-tooltip.html.wide="detailsHtml"
      :aria-label="conditionLabel"
    >
      <i class="bi weather-icon" :class="weatherIconClass"></i>
      <span v-if="formattedTemperature" class="weather-temp">{{ formattedTemperature }}</span>
    </div>

    <!-- Full: every block laid out inline. Used in the mobile drawer card. -->
    <template v-else>
      <div v-if="displayedTime" class="weather-datetime">
        <i class="bi bi-calendar-event"></i>
        <span>{{ displayedTime }}</span>
      </div>
      <div v-if="displayedTime" class="weather-divider"></div>
      <div
        v-if="weather.temperature != null"
        class="weather-condition"
        v-bs-tooltip="conditionLabel"
      >
        <i class="bi weather-icon" :class="weatherIconClass"></i>
        <span class="weather-temp">{{ formattedTemperature }}</span>
      </div>
      <div v-if="weather.wind_speed != null" class="weather-divider"></div>
      <div v-if="weather.wind_speed != null" class="weather-wind">
        <div class="weather-compass">
          <i class="bi bi-arrow-up-short" :style="windArrowStyle"></i>
        </div>
        <div class="weather-wind-block">
          <span class="weather-wind-direction">{{ weather.wind_direction_compass }}</span>
          <span class="weather-wind-speed">{{ weather.wind_speed }} {{ windSpeedUnitLabel }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import { useWeather } from '../../composables/useWeather.js'

defineProps({
  compact: {
    type: Boolean,
    default: false,
  },
})

const { t } = useI18n()
const { weather, start, stop } = useWeather()

let serverTimeAtFetch = null
let clientTimeAtFetch = null
const displayedTime = ref('')
let clockIntervalId = null

function _tick() {
  if (serverTimeAtFetch === null) return
  const elapsedMs = Date.now() - clientTimeAtFetch
  displayedTime.value = serverTimeAtFetch.add(elapsedMs, 'millisecond').format('ddd D MMM · HH:mm')
}

watch(
  () => weather.value?.local_time,
  (localTime) => {
    if (!localTime) return
    serverTimeAtFetch = dayjs(localTime)
    clientTimeAtFetch = Date.now()
    _tick()
  },
)

onMounted(() => {
  start()
  clockIntervalId = setInterval(_tick, 1000)
})

onUnmounted(() => {
  stop()
  if (clockIntervalId !== null) clearInterval(clockIntervalId)
})

const _WEATHER_ICONS = {
  clear_day: 'bi-sun',
  clear_night: 'bi-moon-stars',
  cloudy: 'bi-clouds',
  fog: 'bi-cloud-fog2',
  rain: 'bi-cloud-rain',
  snow: 'bi-cloud-snow',
  thunderstorm: 'bi-cloud-lightning-rain',
  unknown: 'bi-thermometer-half',
}

const weatherIconClass = computed(
  () => _WEATHER_ICONS[weather.value?.condition] ?? 'bi-thermometer-half',
)

const conditionLabel = computed(() =>
  weather.value?.condition ? t(`weather.conditions.${weather.value.condition}`) : '',
)

const unitSymbol = computed(() => (weather.value?.temperature_unit === 'fahrenheit' ? '°F' : '°C'))

const windSpeedUnitLabel = computed(() =>
  weather.value?.wind_speed_unit === 'mph' ? 'mph' : 'km/h',
)

const formattedTemperature = computed(() => {
  if (weather.value?.temperature == null) return ''
  return `${Math.round(weather.value.temperature)}${unitSymbol.value}`
})

const windArrowStyle = computed(() => {
  if (weather.value?.wind_direction_degrees == null) return {}
  return { transform: `rotate(${weather.value.wind_direction_degrees}deg)` }
})

// Markup for the compact chip's hover popover. Every value is app-built (weather
// data and i18n labels, no user input), so the tooltip's `.html` mode is safe.
// Recomputes each second as the live clock ticks, keeping the popover current
// even while hovered.
const detailsHtml = computed(() => {
  const rows = []
  if (displayedTime.value) {
    rows.push(
      `<div class="weather-popover-row"><i class="bi bi-calendar-event"></i>${displayedTime.value}</div>`,
    )
  }
  if (weather.value?.temperature != null) {
    rows.push(
      `<div class="weather-popover-row"><i class="bi ${weatherIconClass.value}"></i>${conditionLabel.value} ${formattedTemperature.value}</div>`,
    )
  }
  if (weather.value?.wind_speed != null) {
    const degrees = weather.value.wind_direction_degrees ?? 0
    rows.push(
      `<div class="weather-popover-row"><i class="bi bi-arrow-up-short weather-popover-arrow" style="transform: rotate(${degrees}deg)"></i>${t('weather.wind')} ${weather.value.wind_direction_compass} ${weather.value.wind_speed} ${windSpeedUnitLabel.value}</div>`,
    )
  }
  return `<div class="weather-popover">${rows.join('')}</div>`
})
</script>

<style scoped>
.weather-widget {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-family: var(--font-sans);
  padding: 0.3rem 0.7rem;
}
.weather-widget-compact {
  padding: 0;
}
.weather-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  cursor: default;
  transition: background 0.12s;
}
.weather-chip:hover {
  background: var(--lichen-pale);
}
.weather-chip .weather-temp {
  font-size: 0.95rem;
}
.weather-datetime {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--slate);
  white-space: nowrap;
}
.weather-condition {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.weather-icon {
  color: var(--lichen);
  font-size: 1.25rem;
}
.weather-temp {
  font-size: 1rem;
  font-weight: 600;
  color: var(--graphite);
}
.weather-divider {
  align-self: stretch;
  width: 1px;
  background: var(--limestone);
}
.weather-wind {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.weather-compass {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border: 1px dashed var(--lichen);
  border-radius: 50%;
  flex-shrink: 0;
}
.weather-compass i {
  color: var(--lichen);
  font-size: 0.8rem;
}
.weather-wind-block {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}
.weather-wind-direction {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--slate);
}
.weather-wind-speed {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--graphite);
  white-space: nowrap;
}
</style>

<!-- Not scoped: Bootstrap appends the tooltip to <body>, out of reach of the
     component's scoped styles. -->
<style>
.weather-popover {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  text-align: left;
}
.weather-popover-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  white-space: nowrap;
}
.weather-popover-row .bi {
  color: var(--lichen-pale);
}
.weather-popover-arrow {
  display: inline-block;
}
</style>
