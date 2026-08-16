import { Tooltip } from 'bootstrap'

// v-bs-tooltip="text" is a Bootstrap hover tooltip. Registered globally in main.js.
// container: 'body' keeps the tooltip from being clipped by overflow parents
// (dropdowns, modals).
//
// Add the `.html` modifier (v-bs-tooltip.html="markup") to render trusted HTML
// content, for example a colour-gradient legend. Sanitisation is disabled in that
// mode, so only ever pass markup the app itself builds, never user input.
// Add the `.wide` modifier to widen the bubble past the default 200px cap
// (see `.bs-tooltip-wide .tooltip-inner` in style.css).
export const bsTooltip = {
  mounted(el, { value, modifiers }) {
    new Tooltip(el, {
      title: value,
      html: modifiers.html || false,
      sanitize: !modifiers.html,
      customClass: modifiers.wide ? 'bs-tooltip-wide' : '',
      trigger: 'hover',
      placement: 'top',
      container: 'body',
    })
  },
  updated(el, { value }) {
    Tooltip.getInstance(el)?.setContent({ '.tooltip-inner': value })
  },
  unmounted(el) {
    Tooltip.getInstance(el)?.dispose()
  },
}
