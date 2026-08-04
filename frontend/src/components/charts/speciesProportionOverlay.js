import { CHART_COLORS } from '../../chartColors.js'

/*
 * Chart.js plugin for the hourly detections chart. While a species is hovered,
 * every bar is drawn in the dimmed colour (see DailyActivityChart's
 * computeBarColors); this plugin paints the hovered species' share of each bar
 * back in the highlight colour.
 *
 * Within each bar the species are stacked in a stable order (highest count
 * first, scientific name as tiebreak), so every species keeps its own band
 * regardless of which one is hovered. Hovering different species in the same
 * bar therefore highlights different segments rather than always the bottom.
 *
 * getHours returns the same hours array the chart is built from (each entry has
 * `count` and a `species_counts` map). getHoveredSpeciesName returns the hovered
 * scientific name, or null when nothing is hovered.
 */
const TOP_CORNER_RADIUS = 3

export function createSpeciesProportionPlugin({ getHours, getHoveredSpeciesName }) {
  return {
    id: 'speciesProportion',
    afterDatasetsDraw(chart) {
      const hoveredSpeciesName = getHoveredSpeciesName()
      if (!hoveredSpeciesName) return

      const hours = getHours()
      const barMeta = chart.getDatasetMeta(0)
      const context = chart.ctx

      hours.forEach((hour, index) => {
        const speciesCounts = hour.species_counts
        const speciesCount = speciesCounts?.[hoveredSpeciesName]
        const totalCount = hour.count || 0
        if (!speciesCount || totalCount <= 0) return

        const bar = barMeta.data[index]
        if (!bar) return

        const { x, y, base, width } = bar.getProps(['x', 'y', 'base', 'width'], true)
        const left = x - width / 2
        const barHeight = base - y
        // Counts stacked below the hovered species set where its band starts.
        const countBelow = sumCountsBelowSpecies(speciesCounts, hoveredSpeciesName)
        const offsetHeight = barHeight * Math.min(countBelow / totalCount, 1)
        const fillHeight = barHeight * Math.min(speciesCount / totalCount, 1)
        const bandTop = base - offsetHeight - fillHeight

        context.save()
        // Clip to the bar's rounded-top shape so the highlight fill matches the
        // bar outline, including when the species accounts for the whole bar.
        clipRoundedTopRect(context, left, y, width, barHeight, TOP_CORNER_RADIUS)
        context.fillStyle = CHART_COLORS.hourlyBarHighlight
        context.fillRect(left, bandTop, width, fillHeight)
        context.restore()
      })
    },
  }
}

function sumCountsBelowSpecies(speciesCounts, hoveredSpeciesName) {
  // Stack species in a stable order (highest count first, scientific name as
  // tiebreak) and sum the counts of every species that sits below the hovered
  // one, so its highlight band always starts at the same offset within the bar.
  const orderedNames = Object.keys(speciesCounts).sort((firstName, secondName) => {
    const countDifference = speciesCounts[secondName] - speciesCounts[firstName]
    if (countDifference !== 0) return countDifference
    return firstName.localeCompare(secondName)
  })
  const hoveredIndex = orderedNames.indexOf(hoveredSpeciesName)
  const namesBelow = orderedNames.slice(0, hoveredIndex)
  return namesBelow.reduce(
    (accumulated, speciesName) => accumulated + speciesCounts[speciesName],
    0,
  )
}

function clipRoundedTopRect(context, left, top, width, height, radius) {
  const clampedRadius = Math.min(radius, width / 2, height)
  const right = left + width
  const bottom = top + height
  context.beginPath()
  context.moveTo(left, bottom)
  context.lineTo(left, top + clampedRadius)
  context.quadraticCurveTo(left, top, left + clampedRadius, top)
  context.lineTo(right - clampedRadius, top)
  context.quadraticCurveTo(right, top, right, top + clampedRadius)
  context.lineTo(right, bottom)
  context.closePath()
  context.clip()
}
