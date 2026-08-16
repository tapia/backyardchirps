<template>
  <Teleport to="body">
    <div class="panel-backdrop" @click="$emit('close')"></div>
    <div class="panel" role="dialog" aria-modal="true">
      <div class="panel-header">
        <button
          type="button"
          class="panel-icon-btn panel-back d-sm-none"
          :aria-label="t('common.back')"
          @click="$emit('close')"
        >
          <i class="bi bi-arrow-left"></i>
        </button>
        <div class="panel-title text-truncate">{{ title }}</div>
        <button
          type="button"
          class="panel-icon-btn panel-close d-none d-sm-inline-flex"
          :aria-label="t('common.close')"
          v-bs-tooltip="t('common.close')"
          @click="$emit('close')"
        >
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
      <div class="panel-body">
        <slot />
      </div>
      <div v-if="$slots.footer" class="panel-footer">
        <slot name="footer" />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

// Shared panel: a full-height sheet on mobile, a centered modal on desktop.
// Purely presentational: it renders the header chrome (a back arrow on mobile,
// a close button on desktop) plus optional footer, and emits `close` from those
// controls or a backdrop tap. The parent owns the open state (mount it with
// v-if) and any Back-button / Escape handling, so hosts that stack several
// panels can coordinate dismissal themselves.
defineProps({
  title: { type: String, required: true },
})

defineEmits(['close'])

const { t } = useI18n()
</script>

<style scoped>
.panel-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1070;
}
.panel {
  position: fixed;
  z-index: 1075;
  display: flex;
  flex-direction: column;
  background: var(--sheet);
  /* Desktop: centered modal. */
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(440px, calc(100vw - 2rem));
  max-height: calc(100vh - 2rem);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.22);
  overflow: hidden;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-soft);
  flex-shrink: 0;
}
.panel-title {
  flex: 1;
  min-width: 0;
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--graphite);
}
.panel-icon-btn {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  border-radius: 50%;
  color: var(--slate);
  font-size: 1rem;
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s;
}
.panel-icon-btn:hover {
  background: var(--paper);
  color: var(--graphite);
}
.panel-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 20px;
}
.panel-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px calc(16px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border-soft);
}

/* Mobile: full-height sheet docked below a small top gap. */
@media (max-width: 575.98px) {
  .panel {
    top: 8px;
    bottom: 0;
    left: 0;
    right: 0;
    transform: none;
    width: auto;
    max-height: none;
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.18);
  }
}
</style>
