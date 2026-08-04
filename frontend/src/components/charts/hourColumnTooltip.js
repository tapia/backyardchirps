import { CHART_COLORS } from '../../chartColors.js'

/*
 * External tooltip for the species-by-hour heatmap: one card per hour column,
 * listing every species detected in that hour. Styled by the .hour-tooltip
 * classes in SpeciesHourlyHeatmapChart.vue.
 *
 * Returns { show, hide, destroy }: call `show` with the content built by the
 * chart plus the anchor it should sit on, and `destroy` when the chart unmounts.
 */

// Above this many species the list splits into two columns so a busy hour
// still fits on screen.
const TWO_COLUMN_THRESHOLD = 14
const VIEWPORT_MARGIN = 12
// Breathing room between the card and the column it describes.
const COLUMN_CLEARANCE = 10

export function createHourColumnTooltip() {
  const tooltipEl = document.createElement('div')
  tooltipEl.className = 'hour-tooltip'
  tooltipEl.style.background = CHART_COLORS.tooltip.background
  tooltipEl.style.borderColor = CHART_COLORS.tooltip.border
  document.body.appendChild(tooltipEl)

  function addChild(parent, tag, className, textContent = '', color = '') {
    const element = document.createElement(tag)
    element.className = className
    if (textContent !== '') element.textContent = textContent
    if (color) element.style.color = color
    parent.appendChild(element)
    return element
  }

  function renderHeader(content) {
    const header = addChild(tooltipEl, 'div', 'hour-tooltip__header')
    addChild(header, 'div', 'hour-tooltip__hour', content.hourLabel, CHART_COLORS.tooltip.title)
    addChild(header, 'div', 'hour-tooltip__total', content.totalLabel, CHART_COLORS.tooltip.body)
  }

  function renderRows(rows) {
    const list = addChild(tooltipEl, 'div', 'hour-tooltip__rows')
    if (rows.length > TWO_COLUMN_THRESHOLD) list.classList.add('hour-tooltip__rows--split')
    for (const row of rows) {
      const item = addChild(list, 'div', 'hour-tooltip__row')
      if (row.highlighted) item.classList.add('hour-tooltip__row--active')
      const nameColor = row.silent ? CHART_COLORS.axis : CHART_COLORS.tooltip.body
      const countColor = row.silent ? CHART_COLORS.axis : CHART_COLORS.tooltip.title
      addChild(item, 'span', 'hour-tooltip__name', row.name, nameColor)
      addChild(item, 'span', 'hour-tooltip__count', row.value, countColor)
    }
  }

  /*
   * Pinned to one edge of the plot instead of trailing the pointer: the card
   * holds still while you sweep across the hours, so only its contents change.
   * It rests on the right and moves to the left edge only once the hovered
   * column would end up underneath it, which depends on how wide the list of
   * species has made the card. `anchor` is { left, right, top, columnX } in
   * viewport coordinates.
   */
  function position(anchor) {
    const { offsetWidth: width, offsetHeight: height } = tooltipEl
    const maxLeft = Math.max(VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN)
    const maxTop = Math.max(VIEWPORT_MARGIN, window.innerHeight - height - VIEWPORT_MARGIN)
    const pinnedRight = anchor.right - width
    const clearsColumn = anchor.columnX < pinnedRight - COLUMN_CLEARANCE
    const edgeLeft = clearsColumn ? pinnedRight : anchor.left

    tooltipEl.style.left = `${Math.min(Math.max(edgeLeft, VIEWPORT_MARGIN), maxLeft)}px`
    tooltipEl.style.top = `${Math.min(Math.max(anchor.top, VIEWPORT_MARGIN), maxTop)}px`
  }

  function show(content, anchor) {
    tooltipEl.innerHTML = ''
    renderHeader(content)
    if (content.rows.length) {
      renderRows(content.rows)
    } else {
      addChild(
        tooltipEl,
        'div',
        'hour-tooltip__empty',
        content.emptyText,
        CHART_COLORS.tooltip.body,
      )
    }
    tooltipEl.classList.add('hour-tooltip--visible')
    position(anchor)
  }

  function hide() {
    tooltipEl.classList.remove('hour-tooltip--visible')
  }

  function destroy() {
    tooltipEl.remove()
  }

  return { show, hide, destroy }
}
