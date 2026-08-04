<template>
  <div ref="rootEl" class="ref-calls-dropdown" :class="{ 'ref-calls-dropdown--up': dropUp }">
    <button
      type="button"
      class="ref-calls-toggle"
      :class="{ 'ref-calls-toggle--open': open }"
      @click="toggle"
    >
      <span class="ref-calls-toggle__label">
        <i class="bi bi-soundwave"></i>{{ t('modal.validateReferenceCalls') }}
      </span>
      <i class="bi" :class="open ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
    </button>
    <div v-if="open" class="ref-calls-body">
      <div v-if="loading" class="text-center text-warm-muted py-3">
        <div class="spinner-border spinner-border-sm"></div>
      </div>
      <ReferenceCallList v-else ref="listEl" :sounds="sounds" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import ReferenceCallList from './ReferenceCallList.vue'

// The reference-calls panel: a toggle that opens a floating list of example
// recordings for the selected species. Self-contained — it owns its open state,
// stops playback when it closes, and dismisses itself on an outside click, so
// callers just pass the sounds and (optionally) call close().
defineProps({
  sounds: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  // Open the panel above the toggle instead of below it.
  dropUp: { type: Boolean, default: false },
})

const { t } = useI18n()

const rootEl = ref(null)
const listEl = ref(null)
const open = ref(false)

// Listen for outside clicks only while open. The list unmounts when we close, so
// stop its playback first. A click inside the panel counts as "inside" the root.
watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('mousedown', onOutsideMouseDown)
  } else {
    listEl.value?.reset()
    document.removeEventListener('mousedown', onOutsideMouseDown)
  }
})

onBeforeUnmount(() => document.removeEventListener('mousedown', onOutsideMouseDown))

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

function onOutsideMouseDown(event) {
  if (rootEl.value && !rootEl.value.contains(event.target)) close()
}

defineExpose({ close })
</script>

<style scoped>
.ref-calls-dropdown {
  position: relative;
}

.ref-calls-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 10px;
  height: 44px;
  background: var(--sheet);
  border: 1px solid var(--dust);
  border-radius: 12px;
  padding: 0 14px;
  cursor: pointer;
  color: var(--graphite);
  transition:
    background 0.12s,
    border-color 0.12s;
}
.ref-calls-toggle:hover {
  background: var(--lichen-pale);
  border-color: var(--lichen);
}
.ref-calls-toggle--open {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}
.ref-calls-toggle__label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
}
.ref-calls-toggle__label .bi-soundwave {
  color: var(--lichen);
  font-size: 0.95rem;
}

.ref-calls-body {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 20;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--dust);
  border-top: none;
  border-radius: 0 0 12px 12px;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
  /* Scroll shadows — see SpeciesSearchPicker for how the layers work. */
  background-color: var(--sheet);
  background-image:
    linear-gradient(var(--sheet) 30%, rgba(var(--sheet-rgb), 0)),
    linear-gradient(rgba(var(--sheet-rgb), 0), var(--sheet) 70%),
    radial-gradient(farthest-side at 50% 0, rgba(0, 0, 0, 0.22), rgba(0, 0, 0, 0)),
    radial-gradient(farthest-side at 50% 100%, rgba(0, 0, 0, 0.22), rgba(0, 0, 0, 0));
  background-position:
    center top,
    center bottom,
    center top,
    center bottom;
  background-size:
    100% 30px,
    100% 30px,
    100% 15px,
    100% 15px;
  background-repeat: no-repeat;
  background-attachment: local, local, scroll, scroll;
}
.ref-calls-body :deep(.stat-card-warm) {
  border: none;
  border-radius: 0;
  background: transparent;
}
.ref-calls-body :deep(.rec-list) {
  margin-top: 0;
  border-top: none;
}

/* Drop-up variant: mirror the fused shape so the panel sits above the toggle. */
.ref-calls-dropdown--up .ref-calls-toggle--open {
  border-radius: 0 0 12px 12px;
}
.ref-calls-dropdown--up .ref-calls-body {
  top: auto;
  bottom: 100%;
  border-top: 1px solid var(--dust);
  border-bottom: none;
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -8px 16px rgba(0, 0, 0, 0.12);
}
</style>
