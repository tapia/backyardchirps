import { readPeriodSelection } from '../periodStorage.js'

// Resolves which time-range selection a species page should start from, keeping
// the localStorage + navigation logic out of the page components themselves.
// Returns a selection object: { preset } or { preset: 'custom', range: [...] }.
export function usePeriodSelection() {
  // Always restore the stored selection so the view survives reloads; falls
  // back to `fallbackPreset` when nothing has been stored yet.
  function restoreSelection(fallbackPreset) {
    return readPeriodSelection() || { preset: fallbackPreset }
  }

  // Restore the stored selection on regular navigation, but start from
  // `fallbackPreset` when the page was opened via a bare link (no in-app
  // history entry) so shared links land on a predictable window.
  function resolveInitialSelection(fallbackPreset) {
    const openedFromLink = window.history.state?.back == null
    return openedFromLink ? { preset: fallbackPreset } : restoreSelection(fallbackPreset)
  }

  return { restoreSelection, resolveInitialSelection }
}
