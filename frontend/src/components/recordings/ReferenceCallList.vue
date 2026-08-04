<template>
  <div class="stat-card-warm p-3">
    <div v-if="!sounds.length" class="text-warm-muted small mt-2">
      {{ t('sound.empty') }}
    </div>

    <div v-else class="rec-list">
      <InlineAudioRow
        v-for="sound in sounds"
        :key="sound.url"
        class="px-2 py-2"
        :url="sound.url"
        :active="isActive(sound.url)"
        @activate="activate(sound.url)"
        @deactivate="deactivate"
      >
        <template #default="{ playing, play }">
          <div class="d-flex align-items-start gap-2">
            <div class="d-flex flex-column align-items-center flex-shrink-0 gap-1">
              <PlayButton small :playing="playing" @click.stop="play" />
              <span v-if="sound.length" class="sound-length">{{ sound.length }}</span>
            </div>

            <div class="flex-grow-1">
              <div class="rec-fields">
                <div class="rec-field">
                  <span class="rec-key">{{ t('sound.type') }}</span
                  ><span class="rec-value" :class="{ 'rec-value--muted': !sound.type }">{{
                    tv(sound.type) || '—'
                  }}</span>
                </div>
                <div class="rec-field">
                  <span class="rec-key">{{ t('sound.sex') }}</span
                  ><span class="rec-value" :class="{ 'rec-value--muted': !sound.sex }">{{
                    tv(sound.sex) || '—'
                  }}</span>
                </div>
                <div class="rec-field">
                  <span class="rec-key">{{ t('sound.stage') }}</span
                  ><span class="rec-value" :class="{ 'rec-value--muted': !sound.stage }">{{
                    tv(sound.stage) || '—'
                  }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </InlineAudioRow>
    </div>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useInlinePlayer } from '../../composables/useInlinePlayer.js'
import InlineAudioRow from './InlineAudioRow.vue'
import PlayButton from '../audio/PlayButton.vue'

// Reference calls for a species (external example recordings from Xeno-Canto),
// shown with their type / sex / stage metadata. Read-only, illustrative — the
// user's own captures live in DetectionRecordingList.
const props = defineProps({
  sounds: { type: Array, default: () => [] },
})

const { t, te } = useI18n()
const { isActive, activate, deactivate, reset } = useInlinePlayer()

// Translate a comma-separated metadata value (e.g. "male, female") using the
// sound.values.* keys, falling back to the raw token when no translation exists.
function tv(value) {
  if (!value) return null
  return value
    .split(',')
    .map((part) => part.trim())
    .map((part) =>
      te(`sound.values.${part.toLowerCase()}`) ? t(`sound.values.${part.toLowerCase()}`) : part,
    )
    .join(', ')
}

watch(() => props.sounds, reset)
defineExpose({ reset })
</script>

<style scoped>
.rec-list {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--limestone);
  margin-top: 8px;
}

.sound-length {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.62rem;
  color: var(--slate);
}

.rec-fields {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.rec-field {
  font-size: 0.75rem;
}
.rec-key {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--slate);
  margin-right: 5px;
}
.rec-value {
  color: var(--graphite);
}
.rec-value--muted {
  color: var(--slate);
}
</style>
