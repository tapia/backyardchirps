<template>
  <div
    ref="rootEl"
    class="search-picker"
    :class="{
      'search-picker--floating': floating,
      'search-picker--open': floating && showResults,
      'search-picker--up': floating && dropUp,
    }"
  >
    <div class="search-field">
      <i class="bi bi-search search-leading-icon"></i>
      <input
        ref="inputEl"
        v-model="query"
        type="text"
        class="form-control search-input"
        :class="{ 'form-control-sm': small }"
        :placeholder="t('search.placeholder')"
        autocomplete="off"
        @input="onQueryInput"
        @keydown.down.prevent="moveActive(1)"
        @keydown.up.prevent="moveActive(-1)"
        @keydown.enter.prevent="chooseActive"
      />
      <button
        v-if="query"
        type="button"
        class="search-clear"
        :aria-label="t('search.clear')"
        @click="onClear"
      >
        <i class="bi bi-x-lg"></i>
      </button>
    </div>
    <div v-if="showResults" class="species-list" :style="{ maxHeight: listHeight + 'px' }">
      <div v-if="searching" class="text-center text-warm-muted py-3">
        <div class="spinner-border spinner-border-sm"></div>
      </div>
      <template v-else>
        <button
          v-for="(species, index) in results"
          :key="species.scientific_name"
          :ref="(el) => setOptionRef(el, index)"
          class="species-option"
          :class="{
            'species-option--selected': species.scientific_name === selectedScientificName,
            'species-option--active': index === activeIndex && !isUnavailable(species),
            'species-option--unavailable': isUnavailable(species),
          }"
          :disabled="isUnavailable(species)"
          @click="onOptionClick(species)"
          @mousemove="activeIndex = index"
        >
          <i v-if="isUnavailable(species)" class="bi bi-lock species-option__lock"></i>
          <img
            v-else
            :src="species.image_url"
            :alt="species.common_name"
            class="species-option__img rounded flex-shrink-0"
            @error="$event.target.style.display = 'none'"
          />
          <span class="species-option__names">
            <span class="species-option__name">{{ species.common_name }}</span>
            <span class="species-option__sci">
              {{ isUnavailable(species) ? unavailableReason : species.scientific_name }}
            </span>
          </span>
          <span v-if="isUnavailable(species)" class="species-option__tag flex-shrink-0">
            {{ unavailableLabel }}
          </span>
          <span v-else-if="selectedScientificName" class="species-option__check flex-shrink-0">
            <i v-if="species.scientific_name === selectedScientificName" class="bi bi-check-lg"></i>
          </span>
        </button>
        <div v-if="!results.length" class="text-warm-muted small px-3 py-2">
          {{ t('search.noResults') }}
        </div>
      </template>
    </div>
    <div v-else-if="!floating" class="text-warm-muted small fst-italic mt-1 search-hint">
      {{ t('search.hint') }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, nextTick, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { searchTaxonomy } from '../../api/index.js'

const MIN_QUERY_LENGTH = 2
const SEARCH_DEBOUNCE_MS = 300

const props = defineProps({
  // When set, the matching result is highlighted with a checkmark.
  selectedScientificName: { type: String, default: '' },
  listHeight: { type: Number, default: 320 },
  small: { type: Boolean, default: false },
  // When true, the results list overlays the content below instead of
  // pushing it down (useful when the picker lives inside a menu/panel).
  floating: { type: Boolean, default: false },
  // When floating, open the results above the input instead of below it
  // (useful when the picker sits near the bottom of its container).
  dropUp: { type: Boolean, default: false },
  // Scientific names that stay visible in the results but cannot be picked, so
  // the reviewer sees why a species is missing rather than it silently vanishing.
  // Both labels are required whenever this is non-empty.
  unavailableScientificNames: { type: Array, default: () => [] },
  unavailableLabel: { type: String, default: '' },
  unavailableReason: { type: String, default: '' },
})

const emit = defineEmits(['select'])

const { t } = useI18n()
const lang = inject('lang')

const rootEl = ref(null)
const inputEl = ref(null)
const query = ref('')
const results = ref([])
const searching = ref(false)
const activeIndex = ref(-1)
const optionEls = ref([])
let debounceTimer = null

const showResults = computed(() => !!query.value.trim() || searching.value)

// In floating mode the results overlay the page, so they must dismiss themselves
// when the user clicks elsewhere. Listen only while results are shown; a click
// inside the picker (including on a result) counts as "inside" so selection is
// not swallowed. Non-floating (inline) usage pushes content and needs no listener.
watch(showResults, (open) => {
  if (!props.floating) return
  if (open) {
    document.addEventListener('mousedown', onOutsideMouseDown)
  } else {
    document.removeEventListener('mousedown', onOutsideMouseDown)
  }
})

onBeforeUnmount(() => document.removeEventListener('mousedown', onOutsideMouseDown))

function onOutsideMouseDown(event) {
  if (rootEl.value && !rootEl.value.contains(event.target)) clear()
}

function onQueryInput() {
  clearTimeout(debounceTimer)
  const trimmed = query.value.trim()
  if (trimmed.length < MIN_QUERY_LENGTH) {
    results.value = []
    searching.value = false
    activeIndex.value = -1
    return
  }
  searching.value = true
  debounceTimer = setTimeout(performSearch, SEARCH_DEBOUNCE_MS)
}

async function performSearch() {
  try {
    const matches = await searchTaxonomy(query.value.trim(), lang.value)
    optionEls.value = []
    activeIndex.value = -1
    results.value = matches.slice().sort((a, b) => a.common_name.localeCompare(b.common_name))
  } finally {
    searching.value = false
  }
}

// Move the keyboard-highlighted result, wrapping around the ends.
function moveActive(delta) {
  const count = results.value.length
  if (!count) return
  if (activeIndex.value === -1) {
    activeIndex.value = delta > 0 ? 0 : count - 1
  } else {
    activeIndex.value = (activeIndex.value + delta + count) % count
  }
  nextTick(() => optionEls.value[activeIndex.value]?.scrollIntoView({ block: 'nearest' }))
}

function isUnavailable(species) {
  return props.unavailableScientificNames.includes(species.scientific_name)
}

function onOptionClick(species) {
  if (isUnavailable(species)) return
  emit('select', species)
}

function chooseActive() {
  if (!results.value.length) return
  const index = activeIndex.value >= 0 ? activeIndex.value : 0
  onOptionClick(results.value[index])
}

function setOptionRef(el, index) {
  if (el) optionEls.value[index] = el
}

function focus() {
  inputEl.value?.focus()
}

function clear() {
  clearTimeout(debounceTimer)
  query.value = ''
  results.value = []
  searching.value = false
  activeIndex.value = -1
}

function onClear() {
  clear()
  focus()
}

defineExpose({ focus, clear })
</script>

<style scoped>
.search-picker--floating {
  position: relative;
}
.search-field {
  position: relative;
}
.search-leading-icon {
  position: absolute;
  top: 50%;
  left: 0.75rem;
  transform: translateY(-50%);
  color: var(--slate);
  font-size: 0.85rem;
  line-height: 1;
  pointer-events: none;
}
.search-input {
  border-color: var(--dust);
  border-radius: 2px;
  font-family: var(--font-sans);
  font-size: 0.85rem;
  padding-left: 2.2rem;
  padding-right: 2.2rem;
}
.search-input:focus {
  border-color: var(--lichen);
  box-shadow: 0 0 0 2px rgba(var(--lichen-rgb), 0.12);
  background-color: #fff;
}

.search-clear {
  position: absolute;
  top: 50%;
  right: 0.5rem;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  padding: 0.3rem;
  color: var(--slate);
  font-size: 0.8rem;
  line-height: 1;
}
.search-clear:hover {
  color: var(--graphite);
}

.search-hint {
  font-size: 0.75rem;
}

.species-list {
  overflow-y: auto;
  margin-top: 0.5rem;
  border: 1px solid var(--limestone);
  border-radius: 2px;
  /* Scroll shadows: a soft shading appears at an edge only while there is more
     content to scroll toward it, and hides once that edge is reached. The cover
     layers scroll with the content (`local`); the shadows stay pinned to the
     viewport (`scroll`), so the covers slide over them at the extremes. */
  background-color: var(--sheet);
  background-image:
    linear-gradient(var(--sheet) 30%, rgba(var(--sheet-rgb), 0)),
    linear-gradient(rgba(var(--sheet-rgb), 0), var(--sheet) 70%),
    radial-gradient(farthest-side at 50% 0, rgba(0, 0, 0, 0.22), rgba(0, 0, 0, 0)),
    radial-gradient(farthest-side at 50% 100%, rgba(0, 0, 0, 0.22), rgba(0, 0, 0, 0));
  background-position:
    center top,
    center bottom,
    center top,
    center bottom;
  background-size:
    100% 30px,
    100% 30px,
    100% 15px,
    100% 15px;
  background-repeat: no-repeat;
  background-attachment: local, local, scroll, scroll;
}
/* When the floating dropdown is open, fuse the input and the list into one
   continuous shape: no gap, flat touching corners, a single shared border. */
.search-picker--floating.search-picker--open .search-input {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}
.search-picker--floating.search-picker--open .search-input:focus {
  box-shadow: none;
}
.search-picker--floating .species-list {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 0;
  border-top: none;
  border-color: var(--dust);
  border-radius: 0 0 12px 12px;
  z-index: 20;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
}

/* Drop-up variant: mirror the fused shape so the list sits above the input. */
.search-picker--floating.search-picker--up.search-picker--open .search-input {
  border-radius: 0 0 12px 12px;
}
.search-picker--floating.search-picker--up .species-list {
  top: auto;
  bottom: 100%;
  border-top: 1px solid var(--dust);
  border-bottom: none;
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -8px 16px rgba(0, 0, 0, 0.12);
}

.species-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: none;
  background: none;
  padding: 6px 10px;
  border-bottom: 1px solid var(--limestone);
  cursor: pointer;
  transition: background 0.1s;
  text-align: left;
}
.species-option:last-child {
  border-bottom: none;
}
.species-option:hover,
.species-option--active {
  background: var(--lichen-pale);
}
.species-option--selected {
  background: rgba(var(--lichen-rgb), 0.1);
}
.species-option--selected:hover {
  background: rgba(var(--lichen-rgb), 0.16);
}

.species-option__img {
  width: 34px;
  height: 34px;
  object-fit: cover;
  flex-shrink: 0;
  border-radius: 1px;
}
.species-option__names {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex-grow: 1;
}
.species-option__name {
  font-family: var(--font-serif);
  font-size: 0.83rem;
  font-weight: 500;
  color: var(--graphite);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.species-option__sci {
  font-family: var(--font-serif);
  font-size: 0.72rem;
  font-style: italic;
  color: var(--slate);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.species-option__check {
  width: 16px;
  font-size: 0.8rem;
  color: var(--lichen);
  text-align: center;
}

/* Still listed, so the reviewer can see the species is accounted for, but not
   selectable: picking it would identify the same bird twice. */
.species-option--unavailable {
  cursor: default;
}
.species-option--unavailable:hover {
  background: none;
}
.species-option--unavailable .species-option__name,
.species-option--unavailable .species-option__sci {
  color: var(--warm-muted);
  font-style: normal;
}
/* The reason has to be readable to do its job, so it wraps rather than
   ellipsing away inside the narrow dropdown. */
.species-option--unavailable .species-option__sci {
  white-space: normal;
  overflow: visible;
  line-height: 1.25;
}
.species-option__lock {
  width: 34px;
  flex-shrink: 0;
  color: var(--warm-muted);
  font-size: 0.85rem;
  text-align: center;
}
.species-option__tag {
  padding: 1px 7px;
  border: 1px solid var(--limestone);
  border-radius: 1px;
  font-family: var(--font-sans);
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--warm-muted);
  background: var(--paper);
}
</style>
