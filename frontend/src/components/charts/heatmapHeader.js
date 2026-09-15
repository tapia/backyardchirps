import { CHART_COLORS } from '../../chartColors.js'

/*
 * ECharts option pieces shared by the two activity heatmaps. Both have a band
 * above the heatmap with one bar per column showing the column total, a "Totals"
 * label lined up with the row labels, and the less/more legend in the top-right
 * corner. The totals use grid, axes and series 0; the heatmap uses index 1 of each.
 */

// Canvas text cannot read CSS custom properties, so the font stacks are written out.
export const AXIS_FONT = "'Helvetica Neue', 'Helvetica', 'Arial', sans-serif"
export const HEADER_FONT = "'Source Sans 3', system-ui, sans-serif"
export const AXIS_TEXT = { color: CHART_COLORS.axis, fontSize: 12, fontFamily: AXIS_FONT }

// Layout from the top: the legend, the totals bars, then the heatmap.
const LEGEND_TOP = 5
const BARS_TOP = 32
const BARS_HEIGHT = 36
export const HEATMAP_TOP = 78
// Row labels end this far from the heatmap.
export const LABEL_GAP = 8
// A bar narrower than this does not show its value.
const MIN_LABELLED_BAR_WIDTH = 18

/*
 * Both areas keep exactly the edges given here. By default ECharts narrows an
 * area whose axis labels would stick out of the chart, and only the heatmap has
 * labels, so its columns would stop lining up with the bars.
 */
export function totalsGrid(plotLeft) {
  return { top: BARS_TOP, height: BARS_HEIGHT, left: plotLeft, right: 0, outerBoundsMode: 'none' }
}

export function heatmapGrid(plotLeft, bottom) {
  return { top: HEATMAP_TOP, bottom, left: plotLeft, right: 0, outerBoundsMode: 'none' }
}

// Its axis line is the rule between the bars and the heatmap.
export function totalsXAxis(columns, extra = {}) {
  return {
    gridIndex: 0,
    type: 'category',
    data: columns,
    axisLine: { lineStyle: { color: CHART_COLORS.activityDivider } },
    axisTick: { show: false },
    axisLabel: { show: false },
    ...extra,
  }
}

// Carries the "Totals" label, which ends where the row labels end.
export function totalsYAxis(t, labelGap = LABEL_GAP) {
  return {
    gridIndex: 0,
    type: 'value',
    max: 'dataMax',
    axisLabel: { show: false },
    splitLine: { show: false },
    name: t('chart.totals'),
    nameLocation: 'middle',
    nameRotate: 0,
    nameGap: labelGap,
    nameTextStyle: { ...AXIS_TEXT, fontFamily: HEADER_FONT, align: 'right' },
  }
}

export function totalsSeries(totals, totalLabels, extra = {}) {
  return {
    type: 'bar',
    xAxisIndex: 0,
    yAxisIndex: 0,
    data: totals.map((total) => total || null),
    barCategoryGap: 1,
    barMinHeight: 2,
    itemStyle: { color: CHART_COLORS.activityBar, borderRadius: [4, 4, 0, 0] },
    label: {
      show: true,
      position: 'top',
      distance: 2,
      formatter: ({ dataIndex }) => totalLabels[dataIndex],
      color: CHART_COLORS.axis,
      fontSize: 12,
      fontWeight: 'bold',
      fontFamily: HEADER_FONT,
    },
    ...extra,
  }
}

// Below this chart width the bars are too narrow to carry their values.
export function narrowBarsWidth(plotLeft, columnCount) {
  return plotLeft + columnCount * (MIN_LABELLED_BAR_WIDTH + 1)
}

// Shades cells by their third value, the colour step from activityLevel().
export function activityLegend(t) {
  return {
    type: 'piecewise',
    seriesIndex: 1,
    dimension: 2,
    pieces: CHART_COLORS.heatmapPalette.map((color, index) => ({ value: index + 1, color })),
    outOfRange: { color: CHART_COLORS.heatmapEmptyCell },
    orient: 'horizontal',
    right: 0,
    top: LEGEND_TOP,
    padding: 0,
    itemWidth: 7,
    itemHeight: 7,
    itemGap: 3,
    itemSymbol: 'rect',
    showLabel: false,
    text: [t('chart.moreActivity'), t('chart.lessActivity')],
    textGap: 6,
    textStyle: { color: CHART_COLORS.activityLabel, fontSize: 10, fontFamily: HEADER_FONT },
    selectedMode: false,
    hoverLink: false,
  }
}

// Colour step of a cell: 0 for none, then 1 to 5 by its share of the maximum.
export function activityLevel(count, maximum) {
  if (count === 0) return 0
  return Math.min(4, Math.floor((count / maximum) * 5)) + 1
}

// data is [column, row, activityLevel, count] per cell.
export function heatmapSeries(data) {
  return {
    type: 'heatmap',
    xAxisIndex: 1,
    yAxisIndex: 1,
    data,
    // Outlined in the card colour to leave a gap between cells.
    itemStyle: { borderColor: CHART_COLORS.heatmapCellGap, borderWidth: 1 },
    emphasis: { disabled: true },
  }
}
