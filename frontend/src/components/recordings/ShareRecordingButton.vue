<template>
  <span v-if="copiedLabelSide === 'start' && shareCopied" class="share-copied-label">
    {{ t('common.copied') }}
  </span>
  <button
    type="button"
    class="share-btn"
    v-bs-tooltip="t('common.shareRecording')"
    :aria-label="t('common.shareRecording')"
    @click.stop="share(shareUrl)"
  >
    <i class="bi" :class="shareCopied ? 'bi-check2' : 'bi-share'"></i>
  </button>
  <span v-if="copiedLabelSide === 'end' && shareCopied" class="share-copied-label">
    {{ t('common.copied') }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useShare } from '../../composables/useShare.js'

// Shares a single captured recording by copying a link to its detail page.
// Standalone so it owns the recording-specific URL and the "Share recording"
// tooltip. Used in the species Recordings tab rows and in the validation dialog.
const props = defineProps({
  recordingId: { type: [Number, String], required: true },
  // Which side of the button the "Copied!" label appears on.
  copiedLabelSide: { type: String, default: 'end' },
})

const { t } = useI18n()
const { shareCopied, share } = useShare()

const shareUrl = computed(() => `${window.location.origin}/recordings/${props.recordingId}`)
</script>

<style scoped>
.share-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border: none;
  background: none;
  padding: 0;
  color: var(--slate);
  font-size: 0.95rem;
  cursor: pointer;
  transition: color 0.12s;
}
.share-btn:hover {
  color: var(--lichen);
}
.share-copied-label {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--lichen);
}
</style>
