<template>
  <div
    class="rec-row rec-row--clickable"
    :class="{ 'rec-row--active': active }"
    @click="onRowClick"
  >
    <slot :active="active" :playing="active && playing" :play="onPlayClick" />

    <SpectrogramPlayer
      v-if="active"
      ref="player"
      v-model:playing="playing"
      :audio-url="url"
      :controls="false"
      :seekable="seekable"
      autoplay
      class="mt-2"
      @click.stop
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import SpectrogramPlayer from '../audio/SpectrogramPlayer.vue'

// A clickable list row that expands into a single inline SpectrogramPlayer.
// The parent list controls which row is active (via the `active` prop) so only
// one plays at a time; the row exposes `active`, `playing`, and a `play`
// callback to its slot for the mode-specific content (fields, badges, buttons).
const props = defineProps({
  url: { type: String, required: true },
  active: { type: Boolean, default: false },
  seekable: { type: Boolean, default: false },
})

const emit = defineEmits(['activate', 'deactivate'])

const player = ref(null)
const playing = ref(false)

// Play button: toggle playback if this row is already open, otherwise open it
// (the SpectrogramPlayer autoplays on mount).
function onPlayClick() {
  if (props.active) player.value?.toggle()
  else emit('activate')
}

// Clicking the row body toggles the inline player open/closed. Interactive
// controls in the slot must use @click.stop so they do not collapse the row.
function onRowClick() {
  emit(props.active ? 'deactivate' : 'activate')
}

// When another row takes over, stop this one before its player unmounts. The
// watcher flushes pre-render, so the player ref is still valid here.
watch(
  () => props.active,
  (isActive) => {
    if (!isActive) player.value?.stop()
  },
)
</script>

<style scoped>
.rec-row {
  transition: background 0.12s;
  border-bottom: 1px solid var(--limestone);
}
.rec-row:last-child {
  border-bottom: none;
}
.rec-row:hover {
  background: var(--lichen-pale);
}
.rec-row--active {
  background: rgba(var(--lichen-rgb), 0.08);
}
.rec-row--clickable {
  cursor: pointer;
}
</style>
