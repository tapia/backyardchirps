<template>
  <div class="d-flex align-items-center flex-wrap gap-2">
    <div v-if="mobileDropdown" class="dropdown d-sm-none">
      <button
        type="button"
        class="btn btn-sm dropdown-toggle"
        :class="`btn-outline-${variant}`"
        data-bs-toggle="dropdown"
      >
        <i class="bi bi-calendar-range me-1"></i>{{ activeMobileLabel }}
      </button>
      <ul class="dropdown-menu">
        <li v-for="p in presets" :key="p.value">
          <button
            type="button"
            class="dropdown-item"
            :class="{ active: activePreset === p.value }"
            @click="selectPreset(p)"
          >
            {{ p.label }}
          </button>
        </li>
        <li><hr class="dropdown-divider" /></li>
        <li>
          <button
            type="button"
            class="dropdown-item"
            :class="{ active: activePreset === 'custom' }"
            @click="openPanel"
          >
            {{ customLabel }}
          </button>
        </li>
      </ul>
    </div>

    <div class="period-btns" :class="{ 'd-none d-sm-inline-flex': mobileDropdown }">
      <button
        v-for="p in presets"
        :key="p.value"
        type="button"
        class="btn btn-sm"
        :class="activePreset === p.value ? `btn-${variant}` : `btn-outline-${variant}`"
        @click="selectPreset(p)"
      >
        {{ p.label }}
      </button>

      <button
        ref="triggerRef"
        type="button"
        class="btn btn-sm period-custom-btn"
        :class="activePreset === 'custom' ? `btn-${variant}` : `btn-outline-${variant}`"
        v-bs-tooltip="activePreset === 'custom' ? customLabel : t('period.custom')"
        @click="openPanel"
      >
        <i class="bi bi-calendar-range"></i>
      </button>
    </div>

    <PeriodRangePanel
      :open="panelOpen"
      :anchor="triggerRef"
      :initial-range="panelInitialRange"
      :max-date="panelMaxDate"
      @apply="onRangeApply"
      @close="panelOpen = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import PeriodRangePanel from './PeriodRangePanel.vue'
import { writePeriodSelection } from '../../periodStorage.js'
import { formatShortDateRange } from '../../dates.js'

const { t, locale } = useI18n()

const props = defineProps({
  variant: { type: String, default: 'primary' },
  defaultPreset: { type: String, default: '24h' },
  mobileDropdown: { type: Boolean, default: false },
  // Optional custom range ([startIso, endIso]) to show as the active selection
  // on load, so a restored custom window highlights correctly without emitting.
  initialRange: { type: Array, default: null },
  // Optional selection to apply and emit on mount, so the parent receives the
  // starting window without duplicating the preset math. Shape mirrors what is
  // stored in localStorage: { preset } or { preset: 'custom', range: [...] }.
  initialSelection: { type: Object, default: null },
})

const emit = defineEmits(['change'])

// stepMs is the navigation step size (full period length).
// For floorDay presets, ms is one day shorter than the label (window starts at midnight),
// so stepMs uses the full label duration for consistent prev/next steps.
const presets = computed(() => [
  {
    value: '24h',
    label: t('period.preset24h'),
    ms: 24 * 60 * 60 * 1000,
    floorDay: false,
    stepMs: 24 * 60 * 60 * 1000,
  },
  {
    value: '7d',
    label: t('period.preset7d'),
    ms: 6 * 24 * 60 * 60 * 1000,
    floorDay: true,
    stepMs: 7 * 24 * 60 * 60 * 1000,
  },
  {
    value: '30d',
    label: t('period.preset30d'),
    ms: 29 * 24 * 60 * 60 * 1000,
    floorDay: true,
    stepMs: 30 * 24 * 60 * 60 * 1000,
  },
  {
    value: '1y',
    label: t('period.preset1y'),
    ms: 364 * 24 * 60 * 60 * 1000,
    floorDay: true,
    stepMs: 365 * 24 * 60 * 60 * 1000,
  },
])

const activePreset = ref(props.initialRange ? 'custom' : props.defaultPreset)
const customRange = ref(
  props.initialRange ? [new Date(props.initialRange[0]), new Date(props.initialRange[1])] : null,
)

const panelOpen = ref(false)
const triggerRef = ref(null)
const panelInitialRange = ref(null)
const panelMaxDate = ref(new Date())

const activeMobileLabel = computed(() => {
  if (activePreset.value === 'custom') return customLabel.value
  return presets.value.find((p) => p.value === activePreset.value)?.label ?? ''
})

const customLabel = computed(() => {
  if (activePreset.value !== 'custom' || !customRange.value) return t('period.custom')
  return formatShortDateRange(customRange.value[0], customRange.value[1], locale.value)
})

watch(
  () => props.defaultPreset,
  (val) => {
    activePreset.value = val
  },
)

function selectPreset(preset) {
  writePeriodSelection({ preset: preset.value })
  _emitPreset(preset)
}

function openPanel() {
  panelMaxDate.value = new Date()
  panelInitialRange.value = seedRange()
  panelOpen.value = true
}

// Seed the picker with the currently applied window so it opens reflecting the
// current view: the saved custom range if any, otherwise the active quick preset.
function seedRange() {
  if (customRange.value) {
    return [new Date(customRange.value[0]), new Date(customRange.value[1])]
  }
  const active = presets.value.find((p) => p.value === activePreset.value)
  const end = new Date()
  const start = active?.ms ? new Date(Date.now() - active.ms) : new Date(Date.now() - 6 * 864e5)
  start.setHours(0, 0, 0, 0)
  return [start, end]
}

function onRangeApply(range) {
  panelOpen.value = false
  if (!range?.[0] || !range?.[1]) return
  writePeriodSelection({
    preset: 'custom',
    range: [new Date(range[0]).toISOString(), new Date(range[1]).toISOString()],
  })
  _emitCustomRange(range)
}

// Sets the active selection and emits the resulting window without persisting.
// User interactions persist first (selectPreset / onRangeApply); the on-mount
// restore reuses these so it does not overwrite the stored selection.
function _emitPreset(preset) {
  activePreset.value = preset.value
  if (preset.ms) {
    const startDate = new Date(Date.now() - preset.ms)
    if (preset.floorDay) startDate.setHours(0, 0, 0, 0)
    emit('change', {
      preset: preset.value,
      start: startDate.toISOString(),
      end: null,
      label: preset.label,
      stepMs: preset.stepMs,
      floorDay: preset.floorDay,
    })
  } else {
    emit('change', {
      preset: 'all',
      start: null,
      end: null,
      label: t('period.allTime'),
      stepMs: null,
      floorDay: false,
    })
  }
}

function _emitCustomRange(range) {
  activePreset.value = 'custom'
  customRange.value = range
  const start = new Date(range[0])
  start.setHours(0, 0, 0, 0)
  const end = new Date(range[1])
  end.setHours(23, 59, 59, 999)
  emit('change', {
    preset: 'custom',
    start: start.toISOString(),
    end: end.toISOString(),
    label: customLabel.value,
    stepMs: end.getTime() - start.getTime(),
    floorDay: false,
  })
}

// Emit the parent-provided starting selection on mount so it receives the
// window without duplicating the preset math. Does not persist, because the parent
// decides what the starting selection is (stored value or a page default).
function _applyInitialSelection(selection) {
  if (selection.preset === 'custom' && selection.range?.length === 2) {
    _emitCustomRange([new Date(selection.range[0]), new Date(selection.range[1])])
    return
  }
  const preset =
    presets.value.find((option) => option.value === selection.preset) ??
    presets.value.find((option) => option.value === props.defaultPreset)
  if (preset) _emitPreset(preset)
}

onMounted(() => {
  if (props.initialSelection) _applyInitialSelection(props.initialSelection)
})
</script>

<style scoped>
/* Segmented quick-preset group with the custom-calendar trigger as the last cell. */
.period-btns {
  display: inline-flex;
  vertical-align: middle;
}
.period-btns .btn {
  border-radius: 0;
  margin-left: -1px;
  position: relative;
  z-index: 0;
}
.period-btns .btn:hover,
.period-btns .btn:focus,
.period-btns .btn:active {
  z-index: 1;
}
.period-btns > .btn:first-child {
  margin-left: 0;
  border-top-left-radius: 2px;
  border-bottom-left-radius: 2px;
}
.period-btns .period-custom-btn {
  border-top-right-radius: 2px;
  border-bottom-right-radius: 2px;
}
</style>
