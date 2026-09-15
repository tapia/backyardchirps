import dayjs from 'dayjs'

// Column label on a detections timeline, e.g. "6AM", "09/13/2026" or "Sep 2026" depending on
// the size of period the API split the timeline into.
export function formatTimelineLabel(isoDate, granularity) {
  if (granularity === 'hour') return dayjs(isoDate).format('hA')
  if (granularity === 'month') return dayjs(isoDate).format('MMM YYYY')
  return dayjs(isoDate).format('L')
}

// Which columns of a detections timeline get a label: every one when the timeline is split
// into hours, otherwise evenly spaced ones, eight at most.
export function timelineLabelIndexes(columnCount, granularity) {
  const maxLabels = granularity === 'hour' ? columnCount : 8
  const step = Math.max(1, Math.ceil(columnCount / maxLabels))
  const indexes = []
  for (let columnIndex = 0; columnIndex < columnCount; columnIndex += step) {
    indexes.push(columnIndex)
  }
  return indexes
}

// Wraps a species name into multiple lines for Chart.js axis tick labels.
// Returns a plain string when it fits on one line, or an array of lines
// (Chart.js renders array tick labels as stacked lines).
export function wrapSpeciesLabel(name, maxChars = 14) {
  const words = name.split(' ')
  const lines = []
  let current = ''
  for (const word of words) {
    const candidate = current ? current + ' ' + word : word
    if (candidate.length > maxChars && current) {
      lines.push(current)
      current = word
    } else {
      current = candidate
    }
  }
  if (current) lines.push(current)
  return lines.length === 1 ? lines[0] : lines
}
