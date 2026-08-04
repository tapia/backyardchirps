import { CHART_COLORS } from '../../chartColors.js'

const HOUR_MS = 3600000

// Which section type starts after each astro event.
const SECTION_AFTER = {
  sunrise: 'day',
  sunset: 'night',
}

// bootstrap-icons glyphs (sun, plain moon) drawn directly on the canvas inside
// each zone. A plain moon (no sparkles) keeps the marker quiet and understated.
const SECTION_ICONS = {
  night: String.fromCodePoint(0xf494),
  day: String.fromCodePoint(0xf5a1),
}

const ICON_FONT_SIZE = 24
// Vertical position of the zone icon, as a fraction of the plot height.
const ICON_TOP_FRACTION = 0.12
// A zone narrower than this many pixels is left without an icon.
const MIN_ICON_ZONE_WIDTH = 34

/*
 * Chart.js plugin that shades an hourly bar chart by day/night, based on
 * sunrise/sunset events: a soft neutral panel behind the bars with a single
 * quiet sun or moon icon inside each zone. The sunrise/sunset legend and
 * navigation live in HTML above the canvas, not here.
 *
 * `getHours` / `getAstro` are accessors so the plugin always reads the
 * component's current props.
 */
export function createDayNightPlugins({ getHours, getAstro }) {
  function msToX(chartInstance, targetMs) {
    const hours = getHours()
    const { chartArea } = chartInstance
    const barMeta = chartInstance.getDatasetMeta(0)
    if (!barMeta.data.length) return null

    const firstMs = new Date(hours[0].hour).getTime()
    const lastMs = new Date(hours[hours.length - 1].hour).getTime()

    if (targetMs <= firstMs) return chartArea.left
    if (targetMs >= lastMs + HOUR_MS) return chartArea.right

    for (let hourIndex = 0; hourIndex < hours.length; hourIndex++) {
      const slotStartMs = new Date(hours[hourIndex].hour).getTime()
      const slotEndMs = slotStartMs + HOUR_MS
      const isLastSlot = hourIndex === hours.length - 1

      if (targetMs >= slotStartMs && (targetMs < slotEndMs || isLastSlot)) {
        const fraction = Math.min((targetMs - slotStartMs) / HOUR_MS, 1)
        const bar = barMeta.data[hourIndex]
        if (!bar) return null
        return bar.x - bar.width / 2 + fraction * bar.width
      }
    }
    return null
  }

  function buildSections(chartInstance) {
    const hours = getHours()
    const astro = getAstro()
    if (!astro?.events || !hours.length) return []
    const barMeta = chartInstance.getDatasetMeta(0)
    if (!barMeta.data.length) return []

    const { chartArea } = chartInstance
    const chartStartMs = new Date(hours[0].hour).getTime()
    const chartEndMs = new Date(hours[hours.length - 1].hour).getTime() + HOUR_MS

    const boundaries = astro.events
      .filter((event) => event.key in SECTION_AFTER)
      .map((event) => ({ ms: new Date(event.time).getTime(), nextType: SECTION_AFTER[event.key] }))
      .sort((a, b) => a.ms - b.ms)

    let currentType = 'night'
    for (const boundary of boundaries) {
      if (boundary.ms <= chartStartMs) currentType = boundary.nextType
    }

    const rawSections = []
    let sectionStartMs = chartStartMs

    for (const boundary of boundaries) {
      if (boundary.ms <= chartStartMs) continue
      if (boundary.ms >= chartEndMs) break
      rawSections.push({ type: currentType, startMs: sectionStartMs, endMs: boundary.ms })
      currentType = boundary.nextType
      sectionStartMs = boundary.ms
    }
    rawSections.push({ type: currentType, startMs: sectionStartMs, endMs: chartEndMs })

    return rawSections.map((section) => ({
      type: section.type,
      startX: msToX(chartInstance, section.startMs) ?? chartArea.left,
      endX: msToX(chartInstance, section.endMs) ?? chartArea.right,
    }))
  }

  function clipPlotArea(ctx, chartArea) {
    // Round the corners of the tinted band so the zones sit as a soft panel
    // behind the bars.
    const radius = 10
    const { left, right, top, bottom } = chartArea
    ctx.beginPath()
    ctx.moveTo(left + radius, top)
    ctx.lineTo(right - radius, top)
    ctx.quadraticCurveTo(right, top, right, top + radius)
    ctx.lineTo(right, bottom - radius)
    ctx.quadraticCurveTo(right, bottom, right - radius, bottom)
    ctx.lineTo(left + radius, bottom)
    ctx.quadraticCurveTo(left, bottom, left, bottom - radius)
    ctx.lineTo(left, top + radius)
    ctx.quadraticCurveTo(left, top, left + radius, top)
    ctx.closePath()
    ctx.clip()
  }

  function drawZoneFills(ctx, chartArea, sections) {
    const areaHeight = chartArea.bottom - chartArea.top
    for (const section of sections) {
      const left = Math.max(section.startX, chartArea.left)
      const right = Math.min(section.endX, chartArea.right)
      if (right <= left) continue
      ctx.fillStyle =
        section.type === 'night' ? CHART_COLORS.dayNight.night : CHART_COLORS.dayNight.day
      ctx.fillRect(left, chartArea.top, right - left, areaHeight)
    }
  }

  function drawZoneIcons(ctx, chartArea, sections) {
    const iconY = chartArea.top + (chartArea.bottom - chartArea.top) * ICON_TOP_FRACTION
    ctx.font = `${ICON_FONT_SIZE}px "bootstrap-icons"`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (const section of sections) {
      const left = Math.max(section.startX, chartArea.left)
      const right = Math.min(section.endX, chartArea.right)
      const width = right - left
      if (width < MIN_ICON_ZONE_WIDTH) continue
      ctx.fillStyle =
        section.type === 'night' ? CHART_COLORS.dayNight.moonIcon : CHART_COLORS.dayNight.sunIcon
      ctx.fillText(SECTION_ICONS[section.type], left + width / 2, iconY)
    }
  }

  const backgroundPlugin = {
    id: 'day-night-background',
    beforeDatasetsDraw(chartInstance) {
      if (!getAstro()?.events || !getHours().length) return
      const { ctx, chartArea } = chartInstance
      if (!chartArea) return

      const sections = buildSections(chartInstance)

      ctx.save()
      clipPlotArea(ctx, chartArea)
      drawZoneFills(ctx, chartArea, sections)
      drawZoneIcons(ctx, chartArea, sections)
      ctx.restore()
    },
  }

  return [backgroundPlugin]
}
