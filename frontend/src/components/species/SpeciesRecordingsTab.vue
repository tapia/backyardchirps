<template>
  <ValidationModal
    ref="validationModal"
    :has-next="false"
    @saved="onRecordingValidated"
    @discarded="onRecordingValidated"
  />

  <div class="rec-section">
    <div
      class="rec-section-header d-flex align-items-center justify-content-between flex-wrap gap-2"
    >
      <span class="d-flex align-items-center gap-2">
        <span class="stat-label">{{ t('modal.allRecordings') }}</span>
        <span class="badge bg-secondary rec-count">{{ total }}</span>
      </span>
      <select v-model="sort" class="form-select form-select-sm sort-select">
        <option value="newest">{{ t('modal.sortNewest') }}</option>
        <option value="oldest">{{ t('modal.sortOldest') }}</option>
        <option value="highest">{{ t('modal.sortHighestConfidence') }}</option>
        <option value="lowest">{{ t('modal.sortLowestConfidence') }}</option>
      </select>
    </div>

    <div v-if="loading && !recordings.length" class="text-center py-4 text-warm-muted">
      <div class="spinner-border spinner-border-sm"></div>
    </div>
    <div v-else-if="!recordings.length" class="text-warm-muted small px-3 py-2">
      {{ t('modal.noRecordings') }}
    </div>
    <template v-else>
      <div class="rec-player-wrap">
        <DetectionRecordingList
          ref="player"
          :recordings="recordings"
          :validate="true"
          :group-by-day="groupByDay"
          @validate="onValidateRecording"
        />
      </div>
      <div v-if="recordings.length < total" class="text-center py-2">
        <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="loadMore">
          {{ t('modal.loadMore') }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '../../api/index.js'
import DetectionRecordingList from '../recordings/DetectionRecordingList.vue'
import ValidationModal from '../review/ValidationModal.vue'

const props = defineProps({
  speciesSlug: { type: String, required: true },
  species: { type: Object, required: true }, // for the validation modal header
})

const emit = defineEmits(['validated'])

// Sort choice lives in the parent so it survives switching tabs.
const sort = defineModel('sort', { type: String, default: 'newest' })

const PAGE_SIZE = 30
const SORT_PARAMS = {
  newest: { sort: 'date', direction: 'desc' },
  oldest: { sort: 'date', direction: 'asc' },
  highest: { sort: 'confidence', direction: 'desc' },
  lowest: { sort: 'confidence', direction: 'asc' },
}

const { t } = useI18n()

// Date sorts read naturally as day-grouped cards; confidence sorts must stay a
// plain ordered list, since grouping by day would scramble the confidence order.
const groupByDay = computed(() => SORT_PARAMS[sort.value].sort === 'date')

const recordings = ref([])
const total = ref(0)
const offset = ref(0)
const loading = ref(false)
const player = ref(null)
const validationModal = ref(null)

async function load(reset = true) {
  if (reset) {
    offset.value = 0
    recordings.value = []
  }
  loading.value = true
  try {
    const data = await api.fetchSpeciesRecordings(props.speciesSlug, {
      ...SORT_PARAMS[sort.value],
      offset: offset.value,
      limit: PAGE_SIZE,
    })
    recordings.value = reset ? data.recordings : [...recordings.value, ...data.recordings]
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  offset.value += PAGE_SIZE
  await load(false)
}

function onValidateRecording(recording) {
  player.value?.reset()
  validationModal.value.open({
    ...recording,
    species: {
      scientific_name: props.species.scientific_name,
      common_name: props.species.common_name,
      image_url: props.species.image_url,
    },
  })
}

async function onRecordingValidated() {
  await load()
  emit('validated')
}

watch(sort, () => load())
onMounted(load)
</script>

<style scoped>
.rec-count {
  font-size: 0.62rem;
}

.rec-section {
  background: var(--sheet);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
  overflow: hidden;
}

.rec-section-header {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-soft);
}

.sort-select {
  width: auto;
  font-size: 0.8rem;
}

.rec-player-wrap :deep(.stat-card-warm) {
  background: none;
  border: none;
  border-radius: 0;
  padding: 0;
}
</style>
