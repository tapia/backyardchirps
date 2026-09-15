import { CHART_COLORS } from '../../chartColors.js'

// Top layout padding a heatmap using this plugin must reserve for the header.
export const HEATMAP_HEADER_HEIGHT = 78
export const TOTALS_BAR_MAX_HEIGHT = 36
// Gap between the foot of the totals bars and the top of the heatmap.
export const TOTALS_BAR_BASE_OFFSET = 10

// Canvas text cannot read CSS custom properties, so the font stack is written out.
const LEGEND_FONT = "10px 'Source Sans 3', system-ui, sans-serif"
const VALUE_LABEL_FONT = "bold 12px 'Source Sans 3', system-ui, sans-serif"
const TOTALS_LABEL_FONT = "12px 'Source Sans 3', system-ui, sans-serif"

const BAR_MIN_HEIGHT = 2
const BAR_MAX_CORNER_RADIUS = 4
// A bar narrower than this shows its value only while its column is hovered.
const BAR_MIN_LABELLED_WIDTH = 18
const SEPARATOR_OFFSET = 8
const LEGEND_TOP = 5
const LEGEND_SWATCH_SIZE = 7
const LEGEND_SWATCH_GAP = 3
const LEGEND_TEXT_GAP = 6

/*
 * Chart.js plugin drawing what sits above a matrix heatmap: one bar per column
 * showing the column total, a line between the bars and the heatmap, a "Totals"
 * label lined up with the Y axis labels, and the less/more activity legend in
 * the top-right corner. The chart must set HEATMAP_HEADER_HEIGHT as its top
 * layout padding.
 *
 * Columns are placed by index on the X scale, which works for both a category
 * scale and a linear one running from -0.5 to columnCount - 0.5.
 *
 * The arguments are accessors so the plugin always reads the component's
 * current props: getColumnTotals returns one total per column (its length is
 * the column count), formatTotal turns a total into the text above its bar,
 * and isColumnHovered(column) draws that column's bar at full strength with
 * its value, however narrow the bar is.
 */
export function createHeatmapHeaderPlugin({
  t,
  getColumnTotals,
  formatTotal = String,
  isColumnHovered = () => false,
}) {
  return {
    id: 'heatmapHeader',
    afterDraw(chart) {
      const ctx = chart.ctx
      ctx.save()
      drawTotalsBars(chart, getColumnTotals(), formatTotal, isColumnHovered)
      drawSeparator(chart)
      drawTotalsLabel(chart, t('chart.totals'))
      drawLegend(chart, t('chart.lessActivity'), t('chart.moreActivity'))
      ctx.restore()
    },
  }
}

function drawTotalsBars(chart, columnTotals, formatTotal, isColumnHovered) {
  const { ctx } = chart
  const xScale = chart.scales.x
  const { top: areaTop, left: areaLeft, right: areaRight } = chart.chartArea
  const barWidth = Math.max(1, (areaRight - areaLeft) / columnTotals.length - 1)
  const cornerRadius = Math.min(BAR_MAX_CORNER_RADIUS, barWidth / 2)
  const barBase = areaTop - TOTALS_BAR_BASE_OFFSET
  const maxTotal = Math.max(...columnTotals, 1)

  columnTotals.forEach((total, column) => {
    if (total === 0) return
    const isHovered = isColumnHovered(column)
    const centerX = xScale.getPixelForValue(column)
    const barHeight = Math.max(BAR_MIN_HEIGHT, (total / maxTotal) * TOTALS_BAR_MAX_HEIGHT)
    const barTop = barBase - barHeight

    ctx.fillStyle = isHovered ? CHART_COLORS.activityBarStrong : CHART_COLORS.activityBar
    topRoundedRectPath(ctx, centerX - barWidth / 2, barTop, barWidth, barHeight, cornerRadius)
    ctx.fill()

    if (barWidth >= BAR_MIN_LABELLED_WIDTH || isHovered) {
      ctx.fillStyle = CHART_COLORS.axis
      ctx.font = VALUE_LABEL_FONT
      ctx.textAlign = 'center'
      ctx.textBaseline = 'bottom'
      ctx.fillText(formatTotal(total), centerX, barTop - 2)
    }
  })
}

function drawSeparator(chart) {
  const { ctx } = chart
  const { top: areaTop, right: areaRight } = chart.chartArea
  ctx.strokeStyle = CHART_COLORS.activityDivider
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(0, areaTop - SEPARATOR_OFFSET)
  ctx.lineTo(areaRight, areaTop - SEPARATOR_OFFSET)
  ctx.stroke()
}

/*
 * Right-aligned where Chart.js draws the Y axis tick labels, so "Totals" reads
 * as one more row label. The position comes from yScale._labelItems, which is
 * private Chart.js API and may change between versions. When it is missing,
 * the fallback repeats Chart.js' own calculation for a left axis:
 * scale.right - (tickLength + tickPadding).
 */
function drawTotalsLabel(chart, text) {
  const { ctx } = chart
  const yScale = chart.scales.y
  const gridTickLength =
    yScale.options.grid?.drawTicks !== false ? (yScale.options.grid?.tickLength ?? 8) : 0
  const tickPadding = yScale.options.ticks?.padding ?? 3
  const tickAnchorX =
    yScale._labelItems?.[0]?.options?.translation?.[0] ??
    yScale.right - gridTickLength - tickPadding
  const barMiddleY = chart.chartArea.top - TOTALS_BAR_BASE_OFFSET - TOTALS_BAR_MAX_HEIGHT / 2

  ctx.font = TOTALS_LABEL_FONT
  ctx.fillStyle = CHART_COLORS.axis
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, tickAnchorX, barMiddleY)
}

function drawLegend(chart, lessText, moreText) {
  const { ctx } = chart
  const palette = CHART_COLORS.heatmapPalette
  ctx.font = LEGEND_FONT
  const lessWidth = ctx.measureText(lessText).width
  const moreWidth = ctx.measureText(moreText).width
  const swatchesWidth =
    palette.length * LEGEND_SWATCH_SIZE + (palette.length - 1) * LEGEND_SWATCH_GAP
  const legendWidth = lessWidth + LEGEND_TEXT_GAP + swatchesWidth + LEGEND_TEXT_GAP + moreWidth
  let cursorX = chart.chartArea.right - legendWidth
  const swatchMiddleY = LEGEND_TOP + LEGEND_SWATCH_SIZE / 2

  ctx.fillStyle = CHART_COLORS.activityLabel
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(lessText, cursorX, swatchMiddleY)
  cursorX += lessWidth + LEGEND_TEXT_GAP

  palette.forEach((color) => {
    ctx.fillStyle = color
    ctx.fillRect(cursorX, LEGEND_TOP, LEGEND_SWATCH_SIZE, LEGEND_SWATCH_SIZE)
    cursorX += LEGEND_SWATCH_SIZE + LEGEND_SWATCH_GAP
  })

  ctx.fillStyle = CHART_COLORS.activityLabel
  ctx.fillText(moreText, cursorX + LEGEND_TEXT_GAP - LEGEND_SWATCH_GAP, swatchMiddleY)
}

function topRoundedRectPath(ctx, x, y, width, height, radius) {
  radius = Math.min(radius, width / 2, height)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.lineTo(x + width - radius, y)
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius)
  ctx.lineTo(x + width, y + height)
  ctx.lineTo(x, y + height)
  ctx.lineTo(x, y + radius)
  ctx.quadraticCurveTo(x, y, x + radius, y)
  ctx.closePath()
}
