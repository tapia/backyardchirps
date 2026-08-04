<template>
  <Teleport to="body">
    <transition :name="isWide ? 'prp-fade' : 'prp-slide'">
      <div v-if="open" class="prp-root" :class="{ 'prp-root--mobile': !isWide }">
        <div class="prp-backdrop" @click="close"></div>

        <div
          ref="panelRef"
          class="prp-panel"
          :class="{ 'prp-panel--mobile': !isWide }"
          :style="isWide ? desktopStyle : undefined"
          role="dialog"
          aria-modal="true"
        >
          <span v-if="isWide" class="prp-tail" :style="{ left: tailLeft + 'px' }"></span>

          <div v-if="!isWide" class="prp-grabber"></div>

          <div class="prp-body">
            <!-- Presets: sidebar on desktop, chip row on mobile -->
            <div class="prp-presets">
              <button
                v-for="preset in rangePresets"
                :key="preset.key"
                type="button"
                class="prp-preset"
                :class="{ 'prp-preset--active': activePresetKey === preset.key }"
                @click="applyPreset(preset)"
              >
                {{ preset.label }}
              </button>
            </div>

            <div class="prp-main">
              <div class="prp-fields-row">
                <div class="prp-fields">
                  <button
                    type="button"
                    class="prp-field"
                    :class="{ 'prp-field--active': selecting === 'start' }"
                    @click="focusField('start')"
                  >
                    <span class="prp-field__label">{{ t('period.from') }}</span>
                    <span class="prp-field__value">
                      {{ draftStart ? formatFieldDate(draftStart) : '—' }}
                    </span>
                    <i class="bi bi-chevron-down prp-field__chevron"></i>
                  </button>
                  <button
                    type="button"
                    class="prp-field"
                    :class="{ 'prp-field--active': selecting === 'end' }"
                    @click="focusField('end')"
                  >
                    <span class="prp-field__label">{{ t('period.to') }}</span>
                    <span class="prp-field__value">
                      {{ draftEnd ? formatFieldDate(draftEnd) : '—' }}
                    </span>
                    <i class="bi bi-chevron-down prp-field__chevron"></i>
                  </button>
                </div>
                <button v-if="isWide" type="button" class="prp-reset" @click="reset">
                  <i class="bi bi-arrow-counterclockwise"></i>{{ t('period.reset') }}
                </button>
              </div>

              <div class="prp-calendars">
                <div v-for="(month, index) in months" :key="index" class="prp-month">
                  <div class="prp-month__nav">
                    <button
                      type="button"
                      class="prp-nav-btn"
                      :aria-label="t('period.from')"
                      @click="navigate(-1)"
                    >
                      <i class="bi bi-chevron-left"></i>
                    </button>
                    <span class="prp-month__title">{{ month.title }}</span>
                    <button
                      type="button"
                      class="prp-nav-btn"
                      :aria-label="t('period.to')"
                      @click="navigate(1)"
                    >
                      <i class="bi bi-chevron-right"></i>
                    </button>
                  </div>
                  <div class="prp-weekdays">
                    <span v-for="label in weekdayLabels" :key="label" class="prp-weekday">
                      {{ label }}
                    </span>
                  </div>
                  <div class="prp-days">
                    <button
                      v-for="cell in month.cells"
                      :key="cell.key"
                      type="button"
                      class="prp-day"
                      :class="cell.stateClass"
                      :disabled="cell.disabled"
                      @click="pickDay(cell)"
                    >
                      <span class="prp-day__inner">{{ cell.day }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="prp-footer">
            <div class="prp-summary">
              <span class="prp-summary__icon"><i class="bi bi-calendar-range"></i></span>
              <div class="prp-summary__text">
                <span class="prp-summary__range">{{ summaryRange }}</span>
                <span class="prp-summary__days">{{ summaryDays }}</span>
              </div>
            </div>
            <div class="prp-actions">
              <button
                v-if="!isWide"
                type="button"
                class="prp-reset prp-reset--inline"
                @click="reset"
              >
                <i class="bi bi-arrow-counterclockwise"></i>{{ t('period.reset') }}
              </button>
              <button type="button" class="btn prp-btn prp-btn--cancel" @click="close">
                {{ t('period.cancel') }}
              </button>
              <button
                type="button"
                class="btn prp-btn prp-btn--apply"
                :disabled="!canApply"
                @click="apply"
              >
                {{ t('period.apply') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'

const { t, locale } = useI18n()

const props = defineProps({
  open: { type: Boolean, default: false },
  anchor: { type: Object, default: null },
  initialRange: { type: Array, default: null },
  maxDate: { type: Date, default: () => new Date() },
})

const emit = defineEmits(['apply', 'close'])

const mediaQuery = window.matchMedia('(min-width: 576px)')
const isWide = ref(mediaQuery.matches)
function onMediaChange(event) {
  isWide.value = event.matches
}
mediaQuery.addEventListener('change', onMediaChange)

// Monday-first for Spanish, Sunday-first otherwise — mirrors the previous
// date-fns locale behaviour.
const weekStart = computed(() => (locale.value === 'es' ? 1 : 0))

const weekdayLabels = computed(() =>
  Array.from({ length: 7 }, (_unused, offset) =>
    dayjs()
      .day((weekStart.value + offset) % 7)
      .format('dd'),
  ),
)

const draftStart = ref(null)
const draftEnd = ref(null)
const selecting = ref(null)
const anchorMonth = ref(dayjs().startOf('month'))

const maxDay = computed(() => dayjs(props.maxDate).endOf('day'))

const rangePresets = computed(() => {
  const end = dayjs().startOf('day')
  return [
    { key: 'last7d', label: t('period.last7d'), start: end.subtract(6, 'day'), end },
    { key: 'last14d', label: t('period.last14d'), start: end.subtract(13, 'day'), end },
    { key: 'last30d', label: t('period.last30d'), start: end.subtract(29, 'day'), end },
    { key: 'last3m', label: t('period.last3m'), start: end.subtract(89, 'day'), end },
    { key: 'last6m', label: t('period.last6m'), start: end.subtract(179, 'day'), end },
    { key: 'thisYear', label: t('period.thisYear'), start: dayjs().startOf('year'), end },
  ]
})

const activePresetKey = computed(() => {
  if (!draftStart.value || !draftEnd.value) return null
  const match = rangePresets.value.find(
    (preset) =>
      preset.start.isSame(draftStart.value, 'day') && preset.end.isSame(draftEnd.value, 'day'),
  )
  return match ? match.key : null
})

const months = computed(() => {
  const list = isWide.value
    ? [anchorMonth.value, anchorMonth.value.add(1, 'month')]
    : [anchorMonth.value]
  return list.map(buildMonth)
})

const canApply = computed(() => Boolean(draftStart.value && draftEnd.value))

const summaryRange = computed(() => {
  if (draftStart.value && draftEnd.value) {
    return `${formatFieldDate(draftStart.value)} – ${formatFieldDate(draftEnd.value)}`
  }
  if (draftStart.value) return formatFieldDate(draftStart.value)
  return '—'
})

const summaryDays = computed(() => {
  if (!draftStart.value || !draftEnd.value) return ''
  const count = draftEnd.value.startOf('day').diff(draftStart.value.startOf('day'), 'day') + 1
  return t('period.nDays', count, { named: { n: count } })
})

// Desktop popover positioning.
const panelRef = ref(null)
const desktopStyle = ref({})
const tailLeft = ref(24)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      initDraft()
      document.addEventListener('keydown', onKeydown, true)
      if (!isWide.value) document.body.classList.add('prp-no-scroll')
      nextTick(updatePosition)
      window.addEventListener('resize', updatePosition)
      window.addEventListener('scroll', updatePosition, true)
    } else {
      teardown()
    }
  },
)

onUnmounted(() => {
  mediaQuery.removeEventListener('change', onMediaChange)
  teardown()
})

function focusField(which) {
  selecting.value = which
}

function pickDay(cell) {
  if (cell.disabled) return
  const day = cell.date
  if (selecting.value === 'start') {
    draftStart.value = day
    if (draftEnd.value && day.isAfter(draftEnd.value, 'day')) draftEnd.value = null
    selecting.value = draftEnd.value ? null : 'end'
  } else if (selecting.value === 'end') {
    if (draftStart.value && day.isBefore(draftStart.value, 'day')) {
      draftEnd.value = draftStart.value
      draftStart.value = day
    } else {
      draftEnd.value = day
    }
    selecting.value = null
  } else if (!draftStart.value || draftEnd.value) {
    draftStart.value = day
    draftEnd.value = null
    selecting.value = 'end'
  } else if (day.isBefore(draftStart.value, 'day')) {
    draftEnd.value = draftStart.value
    draftStart.value = day
    selecting.value = null
  } else {
    draftEnd.value = day
    selecting.value = null
  }
}

function applyPreset(preset) {
  draftStart.value = preset.start.startOf('day')
  draftEnd.value = preset.end.startOf('day')
  selecting.value = null
  anchorMonth.value = draftStart.value.startOf('month')
}

function navigate(delta) {
  anchorMonth.value = anchorMonth.value.add(delta, 'month')
}

function reset() {
  initDraft()
}

function apply() {
  if (!canApply.value) return
  emit('apply', [draftStart.value.startOf('day').toDate(), draftEnd.value.startOf('day').toDate()])
}

function close() {
  emit('close')
}

function formatFieldDate(value) {
  return dayjs(value).format('D MMM YYYY').replace(/\./g, '')
}

function initDraft() {
  if (props.initialRange && props.initialRange[0] && props.initialRange[1]) {
    draftStart.value = dayjs(props.initialRange[0]).startOf('day')
    draftEnd.value = dayjs(props.initialRange[1]).startOf('day')
  } else {
    draftStart.value = null
    draftEnd.value = null
  }
  selecting.value = null
  anchorMonth.value = (draftStart.value ?? dayjs()).startOf('month')
}

function buildMonth(monthStart) {
  const firstOfMonth = monthStart.startOf('month')
  const leadingOffset = (firstOfMonth.day() - weekStart.value + 7) % 7
  const gridStart = firstOfMonth.subtract(leadingOffset, 'day')
  const start = draftStart.value
  const end = draftEnd.value
  const hasRange = Boolean(start && end && !start.isSame(end, 'day'))
  const cells = Array.from({ length: 42 }, (_unused, index) => {
    const date = gridStart.add(index, 'day')
    const disabled = date.isAfter(maxDay.value)
    const isStart = Boolean(start && date.isSame(start, 'day'))
    const isEnd = Boolean(end && date.isSame(end, 'day'))
    const isBetween = Boolean(hasRange && date.isAfter(start, 'day') && date.isBefore(end, 'day'))
    return {
      key: date.valueOf(),
      day: date.date(),
      date,
      disabled,
      stateClass: {
        'prp-day--muted': date.month() !== firstOfMonth.month(),
        'prp-day--single': (isStart || isEnd) && !hasRange,
        'prp-day--start': isStart && hasRange,
        'prp-day--end': isEnd && hasRange,
        'prp-day--between': isBetween,
      },
    }
  })
  return { title: firstOfMonth.format('MMMM YYYY'), cells }
}

function updatePosition() {
  if (!isWide.value || !props.anchor || !panelRef.value) return
  const anchorRect = props.anchor.getBoundingClientRect()
  const panelWidth = panelRef.value.offsetWidth
  const viewportWidth = window.innerWidth
  const margin = 16
  const desiredLeft = anchorRect.left - 24
  const maxLeft = viewportWidth - panelWidth - margin
  const left = Math.max(margin, Math.min(desiredLeft, Math.max(margin, maxLeft)))
  const top = anchorRect.bottom + 10
  desktopStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    maxHeight: `calc(100vh - ${top + margin}px)`,
  }
  const anchorCenter = anchorRect.left + anchorRect.width / 2
  tailLeft.value = Math.max(16, Math.min(anchorCenter - left, panelWidth - 32))
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.stopImmediatePropagation()
    close()
  }
}

function teardown() {
  document.removeEventListener('keydown', onKeydown, true)
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
  document.body.classList.remove('prp-no-scroll')
}
</script>

<style scoped>
.prp-root {
  position: fixed;
  inset: 0;
  z-index: 1080;
}

.prp-backdrop {
  position: absolute;
  inset: 0;
  background: transparent;
}

.prp-root--mobile .prp-backdrop {
  background: rgba(0, 0, 0, 0.4);
}

.prp-panel {
  position: fixed;
  width: min(940px, calc(100vw - 32px));
  background: var(--sheet);
  border: 1px solid var(--limestone);
  border-radius: 4px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.14);
  overflow-y: auto;
  font-family: 'Source Sans 3', system-ui, sans-serif;
}

.prp-tail {
  position: absolute;
  top: -7px;
  width: 12px;
  height: 12px;
  background: var(--sheet);
  border-top: 1px solid var(--limestone);
  border-left: 1px solid var(--limestone);
  transform: rotate(45deg);
}

/* ── Body layout ─────────────────────────────────────────────── */
.prp-body {
  display: flex;
  align-items: stretch;
}

.prp-presets {
  flex: 0 0 200px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 20px 16px;
  border-inline-end: 1px solid var(--limestone);
}

.prp-preset {
  appearance: none;
  border: none;
  background: transparent;
  border-radius: 3px;
  padding: 10px 14px;
  font-size: 0.9rem;
  color: var(--graphite);
  text-align: start;
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s;
}
.prp-preset:hover {
  background: var(--lichen-pale);
}
.prp-preset--active {
  background: var(--lichen-pale);
  color: var(--lichen);
  font-weight: 600;
  box-shadow: inset 3px 0 0 var(--lichen);
}

.prp-main {
  flex: 1 1 auto;
  min-width: 0;
  padding: 20px 24px;
}

/* ── From / To fields + reset ────────────────────────────────── */
.prp-fields-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.prp-fields {
  display: flex;
  gap: 16px;
  flex: 1 1 auto;
  min-width: 0;
}

.prp-field {
  flex: 1 1 0;
  min-width: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 36px 8px 14px;
  background: var(--sheet);
  border: 1px solid var(--limestone);
  border-radius: 4px;
  text-align: start;
  cursor: pointer;
  transition:
    border-color 0.12s,
    box-shadow 0.12s;
}
.prp-field:hover {
  border-color: var(--dust);
}
.prp-field--active {
  border-color: var(--lichen);
  box-shadow: 0 0 0 3px rgba(var(--lichen-rgb), 0.12);
}
.prp-field__label {
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--slate);
}
.prp-field__value {
  font-size: 0.95rem;
  color: var(--graphite);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.prp-field__chevron {
  position: absolute;
  top: 50%;
  inset-inline-end: 14px;
  transform: translateY(-50%);
  font-size: 0.7rem;
  color: var(--slate);
}

.prp-reset {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  appearance: none;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 4px;
  padding: 8px 12px;
  font-size: 0.85rem;
  color: var(--slate);
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s;
}
.prp-reset:hover {
  background: var(--lichen-pale);
  color: var(--lichen);
}
.prp-reset i {
  font-size: 0.9rem;
}

/* ── Calendars ───────────────────────────────────────────────── */
.prp-calendars {
  display: flex;
  gap: 40px;
}

.prp-month {
  flex: 1 1 0;
  min-width: 0;
}

.prp-month__nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.prp-month__title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--graphite);
}
.prp-nav-btn {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--limestone);
  background: var(--sheet);
  border-radius: 4px;
  color: var(--slate);
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s,
    border-color 0.12s;
}
.prp-nav-btn:hover {
  background: var(--lichen-pale);
  border-color: var(--lichen);
  color: var(--lichen);
}

.prp-weekdays,
.prp-days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}
.prp-weekday {
  padding: 4px 0;
  text-align: center;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: lowercase;
  color: var(--slate);
}

.prp-day {
  appearance: none;
  border: none;
  background: transparent;
  padding: 3px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.prp-day__inner {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  font-size: 0.88rem;
  color: var(--graphite);
  border: 1px solid transparent;
  transition:
    background 0.1s,
    color 0.1s;
}
.prp-day:not(:disabled):hover .prp-day__inner {
  background: var(--lichen-pale);
}
.prp-day--muted .prp-day__inner {
  color: var(--dust);
}
.prp-day:disabled {
  cursor: default;
}
.prp-day:disabled .prp-day__inner {
  color: var(--dust);
  opacity: 0.55;
}

/* Range strip — half fills paint the connecting band under start/end. */
.prp-day--between {
  background: var(--lichen-pale);
}
.prp-day--start {
  background: linear-gradient(to right, transparent 50%, var(--lichen-pale) 50%);
}
.prp-day--end {
  background: linear-gradient(to right, var(--lichen-pale) 50%, transparent 50%);
}
.prp-day--single .prp-day__inner,
.prp-day--start .prp-day__inner {
  background: var(--lichen);
  color: #ffffff;
}
.prp-day--start:hover .prp-day__inner,
.prp-day--single:hover .prp-day__inner {
  background: var(--lichen-dark);
}
.prp-day--end .prp-day__inner {
  background: var(--sheet);
  border-color: var(--lichen);
  color: var(--lichen);
  font-weight: 600;
}

/* ── Footer ──────────────────────────────────────────────────── */
.prp-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
  border-top: 1px solid var(--limestone);
}
.prp-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.prp-summary__icon {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--lichen-pale);
  color: var(--lichen);
  font-size: 1.05rem;
}
.prp-summary__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.prp-summary__range {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--graphite);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.prp-summary__days {
  font-size: 0.82rem;
  color: var(--slate);
}

.prp-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}
.prp-btn {
  padding: 8px 22px;
  font-size: 0.9rem;
  border-radius: 4px;
}
.prp-btn--cancel {
  background: var(--sheet);
  border: 1px solid var(--limestone);
  color: var(--graphite);
}
.prp-btn--cancel:hover {
  background: var(--lichen-pale);
  border-color: var(--dust);
}
.prp-btn--apply {
  background: var(--lichen);
  border: 1px solid var(--lichen);
  color: #ffffff;
}
.prp-btn--apply:hover {
  background: var(--lichen-dark);
  border-color: var(--lichen-dark);
}
.prp-btn--apply:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Mobile bottom sheet ─────────────────────────────────────── */
.prp-panel--mobile {
  position: fixed;
  inset: auto 0 0 0;
  width: 100%;
  max-width: 100%;
  max-height: 92vh;
  /* Column layout: grabber + body scroll, footer stays pinned so the primary
     actions are always reachable even when the sheet is taller than the screen. */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: none;
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
  box-shadow: 0 -8px 28px rgba(0, 0, 0, 0.2);
}
.prp-grabber {
  flex: 0 0 auto;
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--limestone);
  margin: 10px auto 4px;
}
.prp-panel--mobile .prp-body {
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.prp-panel--mobile .prp-footer {
  flex: 0 0 auto;
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.prp-panel--mobile .prp-presets {
  flex: 0 0 auto;
  flex-direction: row;
  gap: 8px;
  overflow-x: auto;
  padding: 12px 16px;
  border-inline-end: none;
  border-bottom: 1px solid var(--limestone);
  scrollbar-width: none;
}
.prp-panel--mobile .prp-presets::-webkit-scrollbar {
  display: none;
}
.prp-panel--mobile .prp-preset {
  flex: 0 0 auto;
  border: 1px solid var(--limestone);
  padding: 8px 14px;
  font-size: 0.85rem;
  white-space: nowrap;
}
.prp-panel--mobile .prp-preset--active {
  background: var(--lichen);
  color: #ffffff;
  border-color: var(--lichen);
  box-shadow: none;
}
.prp-panel--mobile .prp-main {
  padding: 16px;
}
.prp-panel--mobile .prp-calendars {
  gap: 0;
}
.prp-panel--mobile .prp-day__inner {
  width: 40px;
  height: 40px;
  font-size: 0.95rem;
}
.prp-panel--mobile .prp-footer {
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
}
.prp-panel--mobile .prp-actions {
  gap: 12px;
}
.prp-panel--mobile .prp-reset--inline {
  border: 1px solid var(--limestone);
  padding: 12px;
  justify-content: center;
}
.prp-panel--mobile .prp-btn {
  flex: 1 1 0;
  padding: 12px;
  font-size: 0.95rem;
}
.prp-panel--mobile .prp-btn--apply {
  flex: 2 1 0;
}

/* ── Transitions ─────────────────────────────────────────────── */
.prp-fade-enter-active,
.prp-fade-leave-active {
  transition: opacity 0.15s ease;
}
.prp-fade-enter-from,
.prp-fade-leave-to {
  opacity: 0;
}
.prp-slide-enter-active,
.prp-slide-leave-active {
  transition: opacity 0.2s ease;
}
.prp-slide-enter-active .prp-panel--mobile,
.prp-slide-leave-active .prp-panel--mobile {
  transition: transform 0.24s ease;
}
.prp-slide-enter-from,
.prp-slide-leave-to {
  opacity: 0;
}
.prp-slide-enter-from .prp-panel--mobile,
.prp-slide-leave-to .prp-panel--mobile {
  transform: translateY(100%);
}
</style>
