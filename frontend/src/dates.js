import dayjs from 'dayjs'

// Locale-aware date, e.g. "07/04/2026" / "4/7/2026".
export function formatDate(isoDate) {
  return isoDate ? dayjs(isoDate).format('L') : '—'
}

// Locale-aware date and time, e.g. "07/04/2026 8:15 AM".
export function formatDateTime(isoDate) {
  return isoDate ? dayjs(isoDate).format('L LT') : '—'
}

// Locale-aware time of day, e.g. "8:15 AM".
export function formatTime(isoDate) {
  return isoDate ? dayjs(isoDate).format('LT') : ''
}

// Calendar-day key for grouping, e.g. "2026-07-04".
export function dayKey(isoDate) {
  return isoDate ? dayjs(isoDate).format('YYYY-MM-DD') : ''
}

// Locale-aware full-day heading for a group header, e.g. "July 6, 2026".
export function formatDayHeading(isoDate) {
  return isoDate ? dayjs(isoDate).format('LL') : ''
}

// Elapsed clip time from a number of seconds, e.g. "0:12", "1:05".
export function formatDuration(seconds) {
  if (!isFinite(seconds) || seconds < 0) return '0:00'
  const wholeSeconds = Math.floor(seconds)
  const minutes = Math.floor(wholeSeconds / 60)
  const remainder = wholeSeconds % 60
  return `${minutes}:${remainder.toString().padStart(2, '0')}`
}

// Compact age of a timestamp: "<1m", "45m", "3h", "2d".
export function shortRelativeTime(isoDate) {
  if (!isoDate) return '—'
  const minutes = Math.round((Date.now() - new Date(isoDate).getTime()) / 60000)
  if (minutes < 1) return '<1m'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}
