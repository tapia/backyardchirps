<template>
  <Teleport to="body">
    <div class="image-lightbox" @click="emit('close')">
      <button
        class="btn-close btn-close-white position-fixed top-0 end-0 m-3"
        @click.stop="emit('close')"
      ></button>
      <img :src="src" :alt="alt" class="image-lightbox__img" @click="emit('close')" />
      <!-- Optional overlay content (e.g. a map legend) drawn over the image. -->
      <slot />
    </div>
  </Teleport>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'

defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: '' },
})

const emit = defineEmits(['close'])

function onKeydown(event) {
  if (event.key === 'Escape') {
    // Capture-phase stop so an underlying Bootstrap modal doesn't close too.
    event.stopImmediatePropagation()
    emit('close')
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown, true))
onUnmounted(() => document.removeEventListener('keydown', onKeydown, true))
</script>

<style scoped>
.image-lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.95);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}
.image-lightbox__img {
  max-width: 100%;
  max-height: 100vh;
  object-fit: contain;
}
</style>
