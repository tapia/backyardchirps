import dayjs from 'dayjs'

// Derives at-a-glance highlight facts for a species from data the profile
// already fetches: `hourly` (24 detection counts over the last year) and
// `daily` ({ 'YYYY-MM-DD': count } over the last year). Returns a list of
// plain descriptors; the component translates and formats them.

const PEAK_WINDOW_HOURS = 3
const COMMON_VISITOR_RATIO = 0.6
const FREQUENT_VISITOR_RATIO = 0.25

export function deriveSpeciesHighlights({ hourly, daily }) {
  const highlights = []
  const regularity = _visitorRegularity(daily)
  if (regularity) highlights.push(regularity)
  const peak = _peakActivityWindow(hourly)
  if (peak) highlights.push(peak)
  const streak = _currentStreak(daily)
  if (streak) highlights.push(streak)
  return highlights
}

// Tier based on the share of days with detections since the species first
// appeared within the last-year window.
function _visitorRegularity(daily) {
  const activeDates = Object.keys(daily)
    .filter((date) => daily[date] > 0)
    .sort()
  if (!activeDates.length) return null
  const windowDays = dayjs().diff(dayjs(activeDates[0]), 'day') + 1
  const ratio = activeDates.length / windowDays
  let tier = 'occasional'
  if (ratio >= COMMON_VISITOR_RATIO) tier = 'common'
  else if (ratio >= FREQUENT_VISITOR_RATIO) tier = 'frequent'
  return { type: 'regularity', tier }
}

// Contiguous 3-hour window with the most detections (wrapping past midnight).
function _peakActivityWindow(hourly) {
  if (!hourly?.length || !hourly.some((count) => count > 0)) return null
  let bestStart = 0
  let bestSum = -1
  for (let startHour = 0; startHour < 24; startHour++) {
    let sum = 0
    for (let offset = 0; offset < PEAK_WINDOW_HOURS; offset++) {
      sum += hourly[(startHour + offset) % 24]
    }
    if (sum > bestSum) {
      bestSum = sum
      bestStart = startHour
    }
  }
  return {
    type: 'peak',
    startHour: bestStart,
    endHour: (bestStart + PEAK_WINDOW_HOURS) % 24,
  }
}

// Consecutive days with detections ending today (or yesterday, so an ongoing
// streak is not broken before the species had a chance to show up today).
function _currentStreak(daily) {
  let day = dayjs()
  if (!daily[day.format('YYYY-MM-DD')]) day = day.subtract(1, 'day')
  let days = 0
  while (daily[day.format('YYYY-MM-DD')] > 0) {
    days += 1
    day = day.subtract(1, 'day')
  }
  return days >= 2 ? { type: 'streak', days } : null
}
