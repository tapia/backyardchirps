<template>
  <div class="spectrogram-player">
    <SpectrogramCanvas
      :audio-url="audioUrl"
      :audio-el="audioEl"
      :seekable="seekable"
      class="mb-2"
      @seek="onSeek"
      @seek-end="onSeekEnd"
    />
    <div class="player-controls">
      <template v-if="controls">
        <div v-if="loading" class="spinner-border spinner-border-sm text-warm-muted" role="status">
          <span class="visually-hidden">{{ t('common.loading') }}</span>
        </div>
        <PlayButton v-else :playing="playing" @click="toggle" />
      </template>

      <span class="player-time">{{ formatDuration(currentTime) }}</span>

      <input
        v-if="seekable"
        class="player-scrubber"
        type="range"
        min="0"
        :max="duration || 1"
        step="0.01"
        :value="currentTime"
        @input="onScrubberInput"
        @change="onSeekEnd"
      />
      <div v-else class="player-progress">
        <div class="player-progress__fill" :style="{ width: progressPct + '%' }"></div>
      </div>

      <span class="player-time">{{ formatDuration(duration) }}</span>
    </div>

    <audio
      ref="audioEl"
      :src="audioUrl ?? ''"
      loop
      preload="auto"
      @play="playing = true"
      @pause="playing = false"
      @ended="onEnded"
      @timeupdate="onTimeUpdate"
      @loadedmetadata="onLoadedMetadata"
      @durationchange="onDurationChange"
      @canplay="loading = false"
      @playing="loading = false"
      @waiting="loading = true"
    ></audio>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import SpectrogramCanvas from './SpectrogramCanvas.vue'
import PlayButton from './PlayButton.vue'
import { useAudioPlayer } from '../../composables/useAudioPlayer.js'
import { formatDuration } from '../../dates.js'

const props = defineProps({
  audioUrl: { type: String, default: null },
  // Show the built-in play/pause button. Set false when a parent (e.g. a list
  // row header) already provides one and drives this player via toggle().
  controls: { type: Boolean, default: true },
  // Allow seeking by tapping/dragging the spectrogram or scrubber. Disabled for
  // externally-streamed clips (reference calls) that don't support range seeks.
  seekable: { type: Boolean, default: true },
  // Start playing as soon as the clip is set (used when a list row activates).
  autoplay: { type: Boolean, default: false },
})

const playingModel = defineModel('playing', { type: Boolean, default: false })

const { t } = useI18n()

const loading = ref(false)

const {
  audioEl,
  playing,
  progressPct,
  duration,
  currentTime,
  onLoadedMetadata,
  onDurationChange,
  onTimeUpdate,
  onEnded,
  toggle,
} = useAudioPlayer()

// Mirror internal playback state out to the optional v-model:playing.
watch(playing, (value) => {
  playingModel.value = value
})

// A new clip reloads the element: reset playback state and show the spinner
// until the browser reports it can play (`@canplay`/`@playing`).
watch(
  () => props.audioUrl,
  (url) => {
    playing.value = false
    loading.value = Boolean(url)
  },
  { immediate: true },
)

onMounted(() => {
  if (props.autoplay && props.audioUrl) audioEl.value?.play()
})

// Move the playback position while dragging the spectrogram or scrubber. The
// audio stays paused during the drag so we don't hear it skip around.
function onSeek(fraction) {
  seekToSeconds(fraction * (audioEl.value?.duration ?? 0))
}

function onScrubberInput(event) {
  seekToSeconds(event.target.valueAsNumber)
}

// Release resumes playback from the final position. play() runs inside the
// pointer gesture, so mobile autoplay policies allow it.
function onSeekEnd() {
  audioEl.value?.play()
}

function stop() {
  const element = audioEl.value
  if (element) {
    element.pause()
    element.currentTime = 0
  }
  playing.value = false
}

function seekToSeconds(seconds) {
  const element = audioEl.value
  if (!element || !isFinite(element.duration) || element.duration <= 0) return
  const clamped = Math.min(Math.max(seconds, 0), element.duration)
  element.pause()
  element.currentTime = clamped
  currentTime.value = clamped
}

defineExpose({ toggle, stop })
</script>

<style scoped>
/* The drawing and its transport read as one card. This lives here rather than
   at a call site so every player looks the same: a caller only positions the
   component, it never restyles it.

   Sizing works the same way for both halves. `aspect-ratio` on the canvas makes
   its height follow its width, and this cap stops both dimensions growing past
   it, so the shape holds at every viewport width. The controls sit inside the
   same cap rather than running the full width of the surrounding page. */
.spectrogram-player {
  --spectrogram-ratio: 3;
  max-width: 720px;
  margin-inline: auto;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  overflow: hidden;
  background: var(--sheet);
}

.player-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 14px 12px;
}

.player-time {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  color: var(--slate);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.player-scrubber {
  flex: 1 1 auto;
  min-width: 0;
  height: 4px;
  accent-color: var(--lichen);
  cursor: pointer;
}

.player-progress {
  flex: 1 1 auto;
  min-width: 0;
  height: 4px;
  background: var(--limestone);
  border-radius: 2px;
  overflow: hidden;
}
.player-progress__fill {
  height: 100%;
  background: var(--lichen);
  border-radius: 2px;
  transition: width 0.25s linear;
}
</style>
