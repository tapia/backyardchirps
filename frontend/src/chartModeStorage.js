// Persisted chart selection for the all-species page. Stored in localStorage
// so the page reopens with the chart the user last chose.
//
// Modes: 'timeline' (species comparison violin) | 'hourly' (species by hour of day).
export const CHART_MODE_STORAGE_KEY = 'speciesListChartMode'

export function readChartMode() {
  try {
    const raw = localStorage.getItem(CHART_MODE_STORAGE_KEY)
    return raw === 'hourly' || raw === 'timeline' ? raw : 'timeline'
  } catch {
    return 'timeline'
  }
}

export function writeChartMode(mode) {
  try {
    localStorage.setItem(CHART_MODE_STORAGE_KEY, mode)
  } catch {
    // Best-effort: ignore storage failures (private mode, quota exceeded).
  }
}
