import dayjs from 'dayjs'

// The shortcuts the period picker offers. Each one is a window that ends now. `unit` and
// `size` give its length, which is also how far "previous" and "next" move it.
//
// The keys are what periodStorage.js saves, so renaming one forgets that choice for anyone
// who had it selected.
export const PERIOD_PRESETS = [
  { key: '24h', labelKey: 'period.last24h', unit: 'hour', size: 24 },
  { key: '7d', labelKey: 'period.last7d', unit: 'day', size: 7 },
  { key: '14d', labelKey: 'period.last14d', unit: 'day', size: 14 },
  { key: '30d', labelKey: 'period.last30d', unit: 'day', size: 30 },
  { key: '3m', labelKey: 'period.last3m', unit: 'day', size: 90 },
  { key: '6m', labelKey: 'period.last6m', unit: 'day', size: 180 },
  { key: '1y', labelKey: 'period.last1y', unit: 'day', size: 365 },
  { key: 'thisYear', labelKey: 'period.thisYear', unit: 'year', size: 1 },
]

export function findPreset(key) {
  return PERIOD_PRESETS.find((preset) => preset.key === key) ?? null
}

// A stored or page-provided selection in a shape the picker can show: a known preset, or a
// custom range with both dates. Anything else falls back to `fallbackKey`.
export function normalizeSelection(selection, fallbackKey) {
  if (selection?.preset === 'custom' && selection.range?.length === 2) {
    return { preset: 'custom', range: selection.range }
  }
  return { preset: findPreset(selection?.preset)?.key ?? fallbackKey }
}

// The window a selection starts on: the live window of a preset, or the days of a custom
// range.
export function selectionWindow(selection) {
  if (selection.preset === 'custom') return customRangeWindow(selection.range)
  return presetWindow(findPreset(selection.preset), 0)
}

// The window of `preset` moved `offset` periods back. Offset 0 is the live window, which has
// no end so it keeps up with new detections. Day presets start at midnight and include
// today, so "Last 7 days" is today and the six days before it.
export function presetWindow(preset, offset) {
  const liveStart = _presetLiveStart(preset)
  if (offset === 0) return { start: liveStart.toDate(), end: null }
  const start = liveStart.subtract(offset * preset.size, preset.unit)
  const end = start.add(preset.size, preset.unit).subtract(1, 'millisecond')
  return { start: start.toDate(), end: end.toDate() }
}

// A custom range covers whole days, from the start of its first day to the end of its last.
export function customRangeWindow(range) {
  return {
    start: dayjs(range[0]).startOf('day').toDate(),
    end: dayjs(range[1]).endOf('day').toDate(),
  }
}

// A custom window moved by its own length, back (-1) or forward (1). Moving forward never
// passes today: a step that would goes to the window of the same length that ends today.
export function shiftCustomWindow(window, direction) {
  const days = _dayCount(window)
  const start = dayjs(window.start).add(direction * days, 'day')
  const end = dayjs(window.end).add(direction * days, 'day')
  if (end.isAfter(dayjs(), 'day')) return latestCustomWindow(window)
  return { start: start.toDate(), end: end.toDate() }
}

// The window with the same number of days as `window` that ends today.
export function latestCustomWindow(window) {
  const today = dayjs()
  return {
    start: today
      .subtract(_dayCount(window) - 1, 'day')
      .startOf('day')
      .toDate(),
    end: today.endOf('day').toDate(),
  }
}

function _presetLiveStart(preset) {
  if (preset.unit === 'hour') return dayjs().subtract(preset.size, 'hour')
  if (preset.unit === 'year') return dayjs().startOf('year')
  return dayjs()
    .startOf('day')
    .subtract(preset.size - 1, 'day')
}

function _dayCount(window) {
  return dayjs(window.end).startOf('day').diff(dayjs(window.start).startOf('day'), 'day') + 1
}
