import dayjs from 'dayjs'

// Column label on a detections timeline, e.g. "6AM", "09/13/2026" or "Sep 2026" depending on
// the size of period the API split the timeline into.
export function formatTimelineLabel(isoDate, granularity) {
  if (granularity === 'hour') return dayjs(isoDate).format('hA')
  if (granularity === 'month') return dayjs(isoDate).format('MMM YYYY')
  return dayjs(isoDate).format('L')
}

// Hour of the day (0 to 23) as "12AM", "6AM", "3PM".
export function formatHourOfDay(hour) {
  return `${hour % 12 || 12}${hour < 12 ? 'AM' : 'PM'}`
}

// Which columns of a detections timeline get a label: every one when the timeline is split
// into hours, otherwise evenly spaced ones, eight at most.
export function timelineLabelIndexes(columnCount, granularity) {
  const step = timelineLabelStep(columnCount, granularity)
  const indexes = []
  for (let columnIndex = 0; columnIndex < columnCount; columnIndex += step) {
    indexes.push(columnIndex)
  }
  return indexes
}

// Every how many columns a detections timeline gets a label, following the same rule.
export function timelineLabelStep(columnCount, granularity) {
  const maxLabels = granularity === 'hour' ? columnCount : 8
  return Math.max(1, Math.ceil(columnCount / maxLabels))
}

// Breaks a species name into lines of at most maxChars, joined by "\n", for chart
// text that does not wrap by itself. A single word longer than that keeps its line.
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
  return lines.join('\n')
}
