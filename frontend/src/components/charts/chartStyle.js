import { CHART_COLORS } from '../../chartColors.js'

/*
 * What every ECharts chart shares: the font stacks and the look of the tooltip.
 * Canvas text cannot read CSS custom properties, so the stacks are written out
 * here, once.
 */

// Axis text: the stack the charts have always used (it was Chart.js' default).
export const AXIS_FONT = "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif"
// The site's --font-sans, for chart text that belongs with the page: legends,
// totals, and the HTML tooltip cards.
export const HEADER_FONT = "'Source Sans 3', system-ui, sans-serif"

export function axisText(fontSize) {
  return { color: CHART_COLORS.axis, fontSize, fontFamily: AXIS_FONT }
}

/*
 * The dark tooltip card. A chart adds its formatter, and overrides the padding
 * or the text style where its card needs them.
 */
export const TOOLTIP_STYLE = {
  backgroundColor: CHART_COLORS.tooltip.background,
  borderColor: CHART_COLORS.tooltip.border,
  borderWidth: 1,
  padding: 10,
  textStyle: { color: CHART_COLORS.tooltip.body, fontSize: 12, fontFamily: AXIS_FONT },
  extraCssText: 'border-radius: 2px; box-shadow: none;',
}
