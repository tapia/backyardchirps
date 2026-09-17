<template>
  <div class="d-inline-flex">
    <div class="btn-group btn-group-sm" role="group">
      <button
        type="button"
        class="btn"
        :class="`btn-outline-${variant}`"
        v-bs-tooltip="t('period.prevPeriod')"
        :aria-label="t('period.prevPeriod')"
        @click="move(-1)"
      >
        <i class="bi bi-chevron-left"></i>
      </button>
      <button
        ref="triggerRef"
        type="button"
        class="btn period-range-btn"
        :class="`btn-outline-${variant}`"
        :aria-expanded="panelOpen"
        aria-haspopup="dialog"
        @click="openPanel"
      >
        <i class="bi bi-calendar-range"></i>
        <span class="period-range-btn__label">{{ label }}</span>
        <i class="bi bi-chevron-down period-range-btn__caret"></i>
      </button>
      <button
        type="button"
        class="btn"
        :class="`btn-outline-${variant}`"
        :disabled="isLatest"
        v-bs-tooltip="t('period.nextPeriod')"
        :aria-label="t('period.nextPeriod')"
        @click="move(1)"
      >
        <i class="bi bi-chevron-right"></i>
      </button>
      <button
        type="button"
        class="btn"
        :class="`btn-outline-${variant}`"
        :disabled="isLatest"
        v-bs-tooltip="t('period.now')"
        :aria-label="t('period.now')"
        @click="goToLatest"
      >
        <i class="bi bi-chevron-double-right"></i>
      </button>
    </div>

    <PeriodRangePanel
      :open="panelOpen"
      :anchor="triggerRef"
      :initial-range="panelInitialRange"
      :active-preset="panelActivePreset"
      :max-date="panelMaxDate"
      @preset="onPresetPick"
      @apply="onRangeApply"
      @close="panelOpen = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import PeriodRangePanel from './PeriodRangePanel.vue'
import { writePeriodSelection } from '../../periodStorage.js'
import { formatShortDateRange } from '../../dates.js'
import {
  findPreset,
  latestCustomWindow,
  normalizeSelection,
  presetWindow,
  selectionWindow,
  shiftCustomWindow,
} from '../../periodPresets.js'

const { t, locale } = useI18n()

const props = defineProps({
  variant: { type: String, default: 'primary' },
  // Selection to start from, in the shape periodStorage.js saves: { preset } or
  // { preset: 'custom', range: [startIso, endIso] }.
  initialSelection: { type: Object, default: () => ({ preset: '24h' }) },
  // Emit the starting window on mount, so a page can load its first data from the picker
  // instead of repeating the period math. A page that has already loaded that window turns
  // it off.
  emitOnMount: { type: Boolean, default: true },
})

const emit = defineEmits(['change'])

// What the user chose. Only this is saved: moving to older periods is not.
const selection = ref(normalizeSelection(props.initialSelection, '24h'))
// How many periods back from a preset's live window. Custom ranges move `shownWindow`
// directly, since "now" for them is not a whole number of steps away.
const offset = ref(0)
const shownWindow = ref(selectionWindow(selection.value))

const panelOpen = ref(false)
const triggerRef = ref(null)
const panelInitialRange = ref(null)
const panelMaxDate = ref(new Date())

const activePreset = computed(() => findPreset(selection.value.preset))
const isLivePreset = computed(() => Boolean(activePreset.value) && offset.value === 0)

const isLatest = computed(() => {
  if (activePreset.value) return offset.value === 0
  return !dayjs(shownWindow.value.end).isBefore(dayjs(), 'day')
})

const label = computed(() => {
  if (isLivePreset.value) return t(activePreset.value.labelKey)
  return formatShortDateRange(shownWindow.value.start, shownWindow.value.end, locale.value)
})

// The shortcut highlighted in the popup: only the live preset, since an older window of
// "Last 7 days" is no longer the last 7 days.
const panelActivePreset = computed(() => (isLivePreset.value ? activePreset.value.key : null))

function move(direction) {
  if (activePreset.value) {
    offset.value = Math.max(0, offset.value - direction)
    shownWindow.value = presetWindow(activePreset.value, offset.value)
  } else {
    shownWindow.value = shiftCustomWindow(shownWindow.value, direction)
  }
  _emitWindow()
}

function goToLatest() {
  if (activePreset.value) {
    offset.value = 0
    shownWindow.value = presetWindow(activePreset.value, 0)
  } else {
    shownWindow.value = latestCustomWindow(shownWindow.value)
  }
  _emitWindow()
}

// Open the popup on the window being shown, including one moved back in time.
function openPanel() {
  panelMaxDate.value = new Date()
  panelInitialRange.value = [
    new Date(shownWindow.value.start),
    shownWindow.value.end ? new Date(shownWindow.value.end) : new Date(),
  ]
  panelOpen.value = true
}

function onPresetPick(key) {
  panelOpen.value = false
  _select({ preset: key })
}

function onRangeApply(range) {
  panelOpen.value = false
  if (!range?.[0] || !range?.[1]) return
  _select({
    preset: 'custom',
    range: [new Date(range[0]).toISOString(), new Date(range[1]).toISOString()],
  })
}

function _select(newSelection) {
  writePeriodSelection(newSelection)
  selection.value = newSelection
  offset.value = 0
  shownWindow.value = selectionWindow(newSelection)
  _emitWindow()
}

// `preset` is the preset key only for a live window. Once moved back it is 'custom', so a
// page labelling the period does not call an older week "Last 7 days". `selection` is what
// the user chose, for a page that has to rebuild the picker later.
function _emitWindow() {
  const { start, end } = shownWindow.value
  emit('change', {
    preset: isLivePreset.value ? activePreset.value.key : 'custom',
    start: new Date(start).toISOString(),
    end: end ? new Date(end).toISOString() : null,
    label: label.value,
    selection: selection.value,
  })
}

onMounted(() => {
  if (props.emitOnMount) _emitWindow()
})
</script>

<style scoped>
.period-range-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 11rem;
  justify-content: center;
}
.period-range-btn__label {
  white-space: nowrap;
}
.period-range-btn__caret {
  font-size: 0.7em;
}
</style>
