<template>
  <div class="d-flex align-items-center gap-3 flex-grow-1">
    <span class="rec-time">{{
      fullDate ? formatDateTime(recording.recorded_at) : formatTime(recording.recorded_at)
    }}</span>
    <span v-if="recording.length_seconds" class="rec-length">
      <i class="bi bi-stopwatch"></i>{{ formatDuration(recording.length_seconds) }}
    </span>
    <div class="ms-auto d-flex align-items-center gap-2">
      <ConfidenceBadge :confidence="recording.confidence" />
      <ShareRecordingButton v-if="showShare" :recording-id="recording.id" />
      <template v-if="showActions">
        <button
          v-if="recording.validation_status === 'pending'"
          type="button"
          class="btn btn-outline-primary review-btn"
          @click.stop="emit('validate', recording)"
        >
          {{ t('modal.review') }}
        </button>
        <button
          v-else
          type="button"
          class="btn edit-btn"
          v-bs-tooltip="t('modal.edit')"
          :aria-label="t('modal.edit')"
          @click.stop="emit('validate', recording)"
        >
          <i class="bi bi-pencil"></i>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { formatTime, formatDateTime, formatDuration } from '../../dates.js'
import ConfidenceBadge from '../common/ConfidenceBadge.vue'
import ShareRecordingButton from './ShareRecordingButton.vue'

// One captured-detection row: time · length · confidence · (optional) action.
// Shared by the species page Recordings tab (day-grouped, with a play button
// and an edit/review action) and the pending-review species view (full date,
// no action, since the whole row opens the validation dialog).
defineProps({
  recording: { type: Object, required: true },
  // Show the review/edit action button. Off where the whole row is clickable.
  showActions: { type: Boolean, default: false },
  // Show the "Share recording" button. On in the species Recordings tab.
  showShare: { type: Boolean, default: false },
  // Show the full date + time instead of just the time. Used where the rows
  // are not already grouped under a day header.
  fullDate: { type: Boolean, default: false },
})

const emit = defineEmits(['validate'])
const { t } = useI18n()
</script>

<style scoped>
.rec-time {
  font-family: var(--font-sans);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--graphite);
}
.rec-length {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: var(--font-sans);
  font-size: 0.8rem;
  color: var(--slate);
}

.review-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  font-family: var(--font-sans);
  font-size: 0.7rem;
  line-height: 1.4;
  padding: 1px 8px;
  white-space: nowrap;
}
.edit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 2px 6px;
  font-size: 0.78rem;
  line-height: 1;
  color: var(--slate);
  border: 1px solid var(--limestone);
  border-radius: 2px;
  background: var(--paper);
  transition:
    color 0.12s,
    border-color 0.12s,
    background 0.12s;
}
.edit-btn:hover {
  color: var(--forest);
  border-color: var(--lichen);
  background: var(--lichen-pale);
}
</style>
