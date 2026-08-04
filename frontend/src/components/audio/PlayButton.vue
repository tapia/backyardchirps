<template>
  <button type="button" class="play-btn" :class="{ 'play-btn--small': small }">
    <i :class="playing ? 'bi bi-pause-fill' : 'bi bi-play-fill'"></i>
  </button>
</template>

<script setup>
defineProps({
  playing: { type: Boolean, required: true },
  small: { type: Boolean, default: false },
})
</script>

<style scoped>
.play-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: var(--lichen);
  color: var(--sheet);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 1.1rem;
  flex-shrink: 0;
  transition: background 0.15s;
}
.play-btn:hover {
  background: var(--lichen-dark);
}
.play-btn--small {
  width: 28px;
  height: 28px;
  font-size: 0.7rem;
}
</style>
