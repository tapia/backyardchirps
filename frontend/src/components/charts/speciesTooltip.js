import { format } from 'echarts/core'
import { CHART_COLORS } from '../../chartColors.js'
import { HEADER_FONT, TOOLTIP_STYLE } from './chartStyle.js'

// Above this many species the list splits into two columns.
const TWO_COLUMN_THRESHOLD = 14

/*
 * The tooltip settings for the card speciesTooltipHtml() builds. A chart adds its own
 * trigger, position and formatter, since each one pins the card to a different place.
 */
export const SPECIES_TOOLTIP = {
  className: 'species-tooltip',
  ...TOOLTIP_STYLE,
  padding: [8, 10],
  textStyle: { fontFamily: HEADER_FONT },
  extraCssText: `${TOOLTIP_STYLE.extraCssText} max-width: calc(100vw - 24px);`,
  confine: true,
}

/*
 * The HTML of a tooltip card that lists every species of one column, such as an hour or a
 * day, laid out by the .species-tooltip__ classes in style.css. Each row is
 * { name, count, active, silent }: count is the text on the right, active marks the species
 * under the pointer, and silent greys out a species not heard in the column. With no rows
 * the card shows emptyText instead of the list.
 */
export function speciesTooltipHtml({ title, summary, rows, emptyText }) {
  const header =
    `<div class="species-tooltip__header">` +
    `<div class="species-tooltip__title" style="color: ${CHART_COLORS.tooltip.title}">` +
    `${format.encodeHTML(title)}</div>` +
    `<div class="species-tooltip__summary" style="color: ${CHART_COLORS.tooltip.body}">` +
    `${format.encodeHTML(summary)}</div></div>`

  if (!rows.length) {
    return (
      header +
      `<div class="species-tooltip__empty" style="color: ${CHART_COLORS.tooltip.body}">` +
      `${format.encodeHTML(emptyText)}</div>`
    )
  }

  const split = rows.length > TWO_COLUMN_THRESHOLD ? ' species-tooltip__rows--split' : ''
  return `${header}<div class="species-tooltip__rows${split}">${rows.map(rowHtml).join('')}</div>`
}

function rowHtml(row) {
  const active = row.active ? ' species-tooltip__row--active' : ''
  const nameColor = row.silent ? CHART_COLORS.axis : CHART_COLORS.tooltip.body
  const countColor = row.silent ? CHART_COLORS.axis : CHART_COLORS.tooltip.title
  return (
    `<div class="species-tooltip__row${active}">` +
    `<span class="species-tooltip__name" style="color: ${nameColor}">` +
    `${format.encodeHTML(row.name)}</span>` +
    `<span class="species-tooltip__count" style="color: ${countColor}">` +
    `${format.encodeHTML(row.count)}</span></div>`
  )
}
