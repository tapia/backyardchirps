import dayjs from 'dayjs'
import { CHART_COLORS } from '../../chartColors.js'

/*
 * External Chart.js tooltip for the hourly detections chart: a floating card
 * showing the hour, total count, and the top species with thumbnails.
 * Styled by the .chart-tooltip classes in DailyActivityChart.vue.
 *
 * Returns { handler, destroy }: pass `handler` as options.plugins.tooltip.external
 * and call `destroy` when the chart unmounts.
 */
export function createHourlyBreakdownTooltip({ getHours, translate }) {
  const tooltipEl = document.createElement('div')
  tooltipEl.className = 'chart-tooltip'
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

  function renderHeader(hourData) {
    const header = addChild(tooltipEl, 'div', 'chart-tooltip__header')
    const time = dayjs(hourData.hour).format('LT')
    addChild(header, 'span', 'chart-tooltip__time', time, CHART_COLORS.tooltip.title)
    addChild(
      header,
      'span',
      'chart-tooltip__header-count',
      `${hourData.count} ${translate('chart.detections')}`,
      CHART_COLORS.tooltip.body,
    )
  }

  function renderSpeciesRow(species) {
    const row = addChild(tooltipEl, 'div', 'chart-tooltip__row')

    const img = addChild(row, 'img', 'chart-tooltip__img')
    img.src = species.image_url
    img.onerror = () => {
      img.style.display = 'none'
    }

    const names = addChild(row, 'div', 'chart-tooltip__names')
    addChild(
      names,
      'div',
      'chart-tooltip__common-name',
      species.common_name,
      CHART_COLORS.tooltip.body,
    )
    addChild(names, 'div', 'chart-tooltip__sci-name', species.scientific_name, CHART_COLORS.axis)

    addChild(row, 'span', 'chart-tooltip__count', species.count, CHART_COLORS.tooltip.title)
  }

  function renderOthersRow(othersCount) {
    const row = addChild(tooltipEl, 'div', 'chart-tooltip__row')
    addChild(row, 'div', 'chart-tooltip__placeholder')
    const names = addChild(row, 'div', 'chart-tooltip__names')
    addChild(
      names,
      'div',
      'chart-tooltip__common-name',
      translate('chart.othersDetections'),
      CHART_COLORS.tooltip.body,
    )
    addChild(row, 'span', 'chart-tooltip__count', othersCount, CHART_COLORS.tooltip.title)
  }

  function positionAtCaret(chart, tooltip) {
    const canvasRect = chart.canvas.getBoundingClientRect()
    const caretX = canvasRect.left + tooltip.caretX
    const caretY = canvasRect.top + tooltip.caretY
    const fitsAbove = caretY - tooltipEl.offsetHeight - 12 >= 0

    tooltipEl.style.left = caretX + 'px'
    tooltipEl.style.top = caretY + 'px'
    tooltipEl.style.transform = fitsAbove
      ? 'translate(-50%, calc(-100% - 12px))'
      : 'translate(-50%, 12px)'
  }

  function handler(context) {
    const { chart, tooltip } = context

    if (tooltip.opacity === 0) {
      tooltipEl.classList.remove('chart-tooltip--visible')
      return
    }

    const dataIndex = tooltip.dataPoints?.[0]?.dataIndex
    const hourData = getHours()[dataIndex]
    if (!hourData) {
      tooltipEl.classList.remove('chart-tooltip--visible')
      return
    }

    tooltipEl.innerHTML = ''
    renderHeader(hourData)

    const topSpecies = hourData.top_species || []
    if (!topSpecies.length) {
      addChild(
        tooltipEl,
        'div',
        'chart-tooltip__empty',
        translate('chart.noDetections'),
        CHART_COLORS.tooltip.body,
      )
    }
    for (const species of topSpecies) {
      renderSpeciesRow(species)
    }

    const topTotal = topSpecies.reduce((sum, species) => sum + species.count, 0)
    const othersCount = hourData.count - topTotal
    if (othersCount > 0) renderOthersRow(othersCount)

    tooltipEl.classList.add('chart-tooltip--visible')
    positionAtCaret(chart, tooltip)
  }

  function destroy() {
    tooltipEl.remove()
  }

  return { handler, destroy }
}
