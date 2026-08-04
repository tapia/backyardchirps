<template>
  <div ref="root" class="navbar-search" :class="{ expanded }" @keydown.esc.prevent="collapse">
    <button
      type="button"
      class="btn btn-outline-primary btn-sm navbar-search-toggle"
      :aria-label="t('search.title')"
      @click="open"
    >
      <i class="bi bi-search"></i>
    </button>
    <div class="navbar-search-panel input-group input-group-sm">
      <SpeciesSearchPicker ref="picker" floating :list-height="320" @select="onSelect" />
      <button
        type="button"
        class="btn btn-outline-primary navbar-search-close"
        :aria-label="t('search.close')"
        @click="collapse"
      >
        <i class="bi bi-x-lg"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import SpeciesSearchPicker from '../species/SpeciesSearchPicker.vue'
import { speciesRoute } from '../../links.js'

// Exposed so the desktop navbar can fade the nav items while the search is open.
const expanded = defineModel('expanded', { type: Boolean, default: false })

const router = useRouter()
const { t } = useI18n()

const root = ref(null)
const picker = ref(null)

watch(expanded, (isOpen) => {
  if (isOpen) {
    nextTick(() => picker.value?.focus())
    // Defer so the click that opened the search doesn't immediately close it.
    nextTick(() => document.addEventListener('mousedown', onOutsideClick))
  } else {
    document.removeEventListener('mousedown', onOutsideClick)
    picker.value?.clear()
  }
})

onBeforeUnmount(() => document.removeEventListener('mousedown', onOutsideClick))

function open() {
  expanded.value = true
}

function collapse() {
  expanded.value = false
}

function onOutsideClick(event) {
  if (root.value && !root.value.contains(event.target)) collapse()
}

function onSelect(species) {
  router.push(speciesRoute(species.slug))
  collapse()
}
</script>

<style scoped>
.navbar-search {
  position: relative;
  display: flex;
  align-items: center;
}
.navbar-search-toggle {
  flex-shrink: 0;
}
.navbar-search.expanded .navbar-search-toggle {
  visibility: hidden;
}

/* The expanded search is an overlay anchored to the toggle's right edge, so it
   grows leftwards without reflowing (and moving) the rest of the navbar. */
.navbar-search-panel {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 280px;
  max-width: 0;
  flex-wrap: nowrap;
  opacity: 0;
  visibility: hidden;
  overflow: hidden;
  transition:
    max-width 0.25s ease,
    opacity 0.2s ease;
}
.navbar-search.expanded .navbar-search-panel {
  max-width: 280px;
  opacity: 1;
  visibility: visible;
  overflow: visible;
}
.navbar-search-panel :deep(.search-picker) {
  flex: 1 1 auto;
  min-width: 0;
}
/* Square off the input's right edge so it fuses with the close button. */
.navbar-search-panel :deep(.search-input) {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}
.navbar-search-close {
  flex-shrink: 0;
}
</style>
