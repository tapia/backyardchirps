// Persisted time-range selection for the species period picker. Stored in
// localStorage and shared across pages so the picker keeps the user's chosen
// window instead of resetting to the default on navigation or reload.
//
// Shape: { preset: '24h' | '7d' | '30d' | '1y' } for quick presets, or
// { preset: 'custom', range: [startIso, endIso] } for a custom range.
export const PERIOD_STORAGE_KEY = 'speciesPeriodSelection'

export function readPeriodSelection() {
  try {
    const raw = localStorage.getItem(PERIOD_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function writePeriodSelection(selection) {
  try {
    localStorage.setItem(PERIOD_STORAGE_KEY, JSON.stringify(selection))
  } catch {
    // Best-effort: ignore storage failures (private mode, quota exceeded).
  }
}
