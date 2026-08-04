<template>
  <Teleport to="body">
    <div class="confirm-backdrop" @click="requestCancel"></div>
    <div class="confirm-dialog" role="alertdialog" aria-modal="true" :aria-label="title">
      <div class="confirm-body">
        <span class="confirm-icon" :class="{ 'confirm-icon--danger': danger }" aria-hidden="true">
          <i class="bi" :class="danger ? 'bi-exclamation-triangle' : 'bi-question-circle'"></i>
        </span>
        <div class="min-w-0">
          <div class="confirm-title">{{ title }}</div>
          <div v-if="message" class="confirm-message">{{ message }}</div>
          <!-- Optional block, to fill when a more detailed explanation is needed -->
          <slot></slot>
        </div>
      </div>

      <div class="confirm-footer">
        <button type="button" class="btn confirm-cancel" :disabled="busy" @click="requestCancel">
          {{ cancelLabel || t('common.cancel') }}
        </button>
        <button
          type="button"
          class="btn confirm-accept"
          :class="danger ? 'btn-danger' : 'btn-primary'"
          :disabled="busy"
          @click="$emit('confirm')"
        >
          <span v-if="busy" class="spinner-border spinner-border-sm me-1"></span>
          {{ confirmLabel }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

// Shared confirmation: a small centered card on every screen size, unlike
// SlidePanel which becomes a full-height sheet on mobile. The parent owns the
// open state (mount it with v-if) and handles `confirm`; dismissal is handled
// here so every host gets Escape and the Back button for free.
const props = defineProps({
  title: { type: String, required: true },
  message: { type: String, default: '' },
  confirmLabel: { type: String, required: true },
  // Defaults to common.cancel; pass one only when a screen needs different wording.
  cancelLabel: { type: String, default: '' },
  // Styles the accept button as destructive and swaps in a warning icon.
  danger: { type: Boolean, default: false },
  // Shows a spinner and blocks both buttons while the action is in flight.
  busy: { type: Boolean, default: false },
  // Push a history entry and claim Escape while open, so both dismiss this
  // dialog. Turn off when a host already stacks layers of its own (e.g. the
  // validation dialog) and needs to decide where this one sits in the order.
  selfDismiss: { type: Boolean, default: true },
})

const emit = defineEmits(['confirm', 'cancel'])

const { t } = useI18n()

// Dismissal, mirroring SpeciesDetectionSettingsModal: Escape and Back both
// cancel, and the pushed entry is unwound on close unless Back consumed it.
let historyPushed = false
let closingFromPopState = false

function requestCancel() {
  // The buttons are disabled mid-flight; keep the backdrop and Escape in step.
  if (props.busy) return
  emit('cancel')
}

function onKeydown(event) {
  if (event.key !== 'Escape') return
  event.stopImmediatePropagation()
  requestCancel()
}

function onPopState() {
  closingFromPopState = true
  emit('cancel')
}

onMounted(() => {
  if (!props.selfDismiss) return
  document.addEventListener('keydown', onKeydown, true)
  window.addEventListener('popstate', onPopState)
  history.pushState({ confirmDialog: true }, '')
  historyPushed = true
})

onUnmounted(() => {
  if (!props.selfDismiss) return
  document.removeEventListener('keydown', onKeydown, true)
  window.removeEventListener('popstate', onPopState)
  if (historyPushed && !closingFromPopState) history.back()
  historyPushed = false
  closingFromPopState = false
})
</script>

<style scoped>
/* Sits above SlidePanel (1070/1075) so it can confirm an action started there. */
.confirm-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1080;
}
.confirm-dialog {
  position: fixed;
  z-index: 1085;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(400px, calc(100vw - 2rem));
  max-height: calc(100dvh - 2rem);
  display: flex;
  flex-direction: column;
  background: var(--sheet);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.22);
  overflow: hidden;
}

.confirm-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 20px;
}
.confirm-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--lichen-rgb), 0.14);
  color: var(--lichen);
  font-size: 1.2rem;
}
.confirm-icon--danger {
  background: rgba(var(--bs-danger-rgb), 0.12);
  color: var(--bs-danger);
}
.confirm-title {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--graphite);
  line-height: 1.25;
}
.confirm-message {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.88rem;
  color: var(--slate);
  margin-top: 6px;
}

.confirm-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px calc(16px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border-soft);
}
.confirm-cancel {
  background: var(--paper);
  border-color: var(--border-soft);
  color: var(--graphite);
}
.confirm-cancel,
.confirm-accept {
  font-weight: 600;
  padding: 8px 18px;
  border-radius: 8px;
}
</style>
