<template>
  <ValidationModal
    ref="validationModal"
    :has-next="hasNextInQueue"
    @saved="onSaved"
    @discarded="onDiscarded"
    @skipped="onSkipped"
    @changed="onSettingsChanged"
  />

  <div class="container pb-5">
    <div
      class="d-flex flex-column flex-sm-row align-items-sm-center justify-content-between gap-3 mb-4"
    >
      <div>
        <h4 class="mb-0">{{ t('page.pending.title') }}</h4>
        <span class="small text-warm-muted">{{
          t('page.pending.count', { n: totalCount, speciesCount })
        }}</span>
      </div>
      <div class="d-flex align-items-center gap-2">
        <span class="small text-warm-muted">{{ t('filter.sortBy') }}</span>
        <div class="btn-group btn-group-sm">
          <button
            class="btn"
            :class="sort === 'date' ? 'btn-primary' : 'btn-outline-primary'"
            @click="setSort('date')"
          >
            <i class="bi bi-calendar3 me-1"></i>{{ t('filter.byDate') }}
          </button>
          <button
            class="btn"
            :class="sort === 'species' ? 'btn-primary' : 'btn-outline-primary'"
            @click="setSort('species')"
          >
            <i class="bi bi-feather me-1"></i>{{ t('filter.bySpecies') }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="text-center py-5 text-warm-muted">
      <div class="spinner-border spinner-border-sm me-2"></div>
      {{ t('common.loading') }}
    </div>

    <div v-else-if="!detections.length" class="text-warm-muted text-center py-5">
      <i class="bi bi-check-circle fs-1 d-block mb-3 opacity-50"></i>
      {{ t('page.pending.empty') }}
    </div>

    <template v-else>
      <!-- Date view: flat chronological list; a row opens the validation modal -->
      <template v-if="sort === 'date'">
        <TransitionGroup tag="div" class="stat-card-warm" name="pending-row">
          <div
            v-for="detection in detections"
            :key="detection.id"
            class="pending-row px-3 py-2"
            :class="{
              'pending-row--validated': justValidatedId === detection.id,
              'pending-row--discarded': justDiscardedId === detection.id,
            }"
            @click="onValidate(detection)"
          >
            <div class="d-flex align-items-center gap-2">
              <button
                class="row-check flex-shrink-0"
                :class="{ 'row-check--on': selectedIds.has(detection.id) }"
                role="checkbox"
                :aria-checked="selectedIds.has(detection.id)"
                :aria-label="t('page.pending.select')"
                @click.stop="toggleSelect(detection.id)"
              >
                <i
                  class="bi"
                  :class="selectedIds.has(detection.id) ? 'bi-check-square-fill' : 'bi-square'"
                ></i>
              </button>
              <img
                :src="detection.species.image_url"
                :alt="detection.species.common_name"
                class="species-thumb rounded flex-shrink-0"
                @error="$event.target.style.display = 'none'"
              />
              <div class="flex-grow-1 min-w-0">
                <div class="fw-semibold small text-truncate text-graphite pending-bird-name">
                  {{ detection.species.common_name }}
                </div>
                <div class="fst-italic text-warm-muted text-truncate pending-sci-name">
                  {{ detection.species.scientific_name }}
                </div>
                <!-- date + confidence shown below name on mobile only -->
                <div class="d-flex d-sm-none align-items-center gap-2 mt-1">
                  <span class="text-warm-muted" style="font-size: 0.75rem">{{
                    formatDateTime(detection.recorded_at)
                  }}</span>
                  <ConfidenceBadge :confidence="detection.confidence" />
                </div>
              </div>
              <!-- date + confidence in the outer row on desktop only -->
              <div class="d-none d-sm-flex align-items-center gap-2 flex-shrink-0">
                <span class="text-warm-muted small">{{
                  formatDateTime(detection.recorded_at)
                }}</span>
                <ConfidenceBadge :confidence="detection.confidence" />
              </div>
            </div>
          </div>
        </TransitionGroup>
      </template>

      <!-- Species view: recordings grouped by species, collapsible -->
      <template v-else>
        <div v-for="group in speciesGroups" :key="group.scientific_name" class="species-group mb-3">
          <div
            class="species-header-wrap d-flex align-items-center"
            :class="{ 'species-header--open': !collapsedSpecies.has(group.scientific_name) }"
          >
            <button
              class="row-check group-check flex-shrink-0 ps-3"
              :class="{ 'row-check--on': groupSelectionState(group) !== 'none' }"
              role="checkbox"
              :aria-checked="groupSelectionState(group) === 'all'"
              :aria-label="t('page.pending.selectGroup')"
              @click="toggleGroup(group)"
            >
              <i class="bi" :class="groupCheckIcon(group)"></i>
            </button>
            <button
              class="species-header flex-grow-1 d-flex align-items-center gap-3 px-3 py-2"
              @click="toggleSpeciesCollapse(group.scientific_name)"
            >
              <img
                :src="group.image_url"
                :alt="group.common_name"
                class="rounded flex-shrink-0"
                style="width: 40px; height: 40px; object-fit: cover"
                @error="$event.target.style.display = 'none'"
              />
              <div class="flex-grow-1 min-w-0 text-start">
                <div class="fw-semibold text-truncate text-graphite pending-bird-name">
                  {{ group.common_name }}
                </div>
                <div class="fst-italic text-warm-muted small text-truncate">
                  {{ group.scientific_name }}
                </div>
              </div>
              <span class="species-count flex-shrink-0">{{ group.recordings.length }}</span>
              <i
                class="bi flex-shrink-0 text-warm-muted"
                :class="
                  collapsedSpecies.has(group.scientific_name)
                    ? 'bi-chevron-right'
                    : 'bi-chevron-down'
                "
              ></i>
            </button>
          </div>
          <div v-if="!collapsedSpecies.has(group.scientific_name)">
            <div
              v-for="recording in group.recordings"
              :key="recording.id"
              class="pending-row px-3 py-2 d-flex align-items-center"
              :class="{
                'pending-row--validated': justValidatedId === recording.id,
                'pending-row--discarded': justDiscardedId === recording.id,
              }"
              @click="onValidate(recording)"
            >
              <button
                class="row-check flex-shrink-0 me-2"
                :class="{ 'row-check--on': selectedIds.has(recording.id) }"
                role="checkbox"
                :aria-checked="selectedIds.has(recording.id)"
                :aria-label="t('page.pending.select')"
                @click.stop="toggleSelect(recording.id)"
              >
                <i
                  class="bi"
                  :class="selectedIds.has(recording.id) ? 'bi-check-square-fill' : 'bi-square'"
                ></i>
              </button>
              <DetectionRecordingRow :recording="recording" full-date />
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>

  <Transition name="action-bar">
    <div v-if="selectedIds.size" class="bulk-action-bar">
      <div class="container bulk-action-inner">
        <span class="bulk-count fw-semibold text-graphite small">{{
          t('page.pending.selected', { n: selectedIds.size })
        }}</span>
        <button
          class="btn btn-sm btn-link bulk-clear text-warm-muted text-decoration-none"
          @click="clearSelection"
        >
          {{ t('page.pending.clearSelection') }}
        </button>
        <div class="bulk-buttons d-flex gap-2">
          <button class="btn btn-sm btn-primary" :disabled="busy" @click="bulkConfirm">
            <i class="bi bi-check-lg me-1"></i
            >{{ t('page.pending.confirmN', { n: selectedIds.size }) }}
          </button>
          <button class="btn btn-sm btn-outline-danger" :disabled="busy" @click="askBulkDelete">
            <i class="bi bi-trash me-1"></i>{{ t('page.pending.deleteN', { n: selectedIds.size }) }}
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <ConfirmDialog
    v-if="showDeleteConfirm"
    :title="t('page.pending.deleteConfirmTitle', { n: selectedIds.size })"
    :message="t('page.pending.deleteConfirmMessage')"
    :confirm-label="t('page.pending.deleteN', { n: selectedIds.size })"
    danger
    :busy="busy"
    @confirm="performBulkDelete"
    @cancel="showDeleteConfirm = false"
  />
</template>

<script setup>
import { ref, computed, inject, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { bulkValidateDetections, fetchDubiousDetections } from '../api/index.js'
import DetectionRecordingRow from '../components/recordings/DetectionRecordingRow.vue'
import ConfidenceBadge from '../components/common/ConfidenceBadge.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import ValidationModal from '../components/review/ValidationModal.vue'
import { useDubiousCount } from '../composables/useDubiousCount.js'
import { formatDateTime } from '../dates.js'

const { t } = useI18n()
const lang = inject('lang')
const { refresh: refreshCount } = useDubiousCount()

const sort = ref('date')
const loading = ref(false)
const detections = ref([])
const totalCount = ref(0)
const validationModal = ref(null)
const collapsedSpecies = ref(new Set())
const speciesOrder = ref([])
const currentDetectionIndex = ref(-1)
const justValidatedId = ref(null)
const justDiscardedId = ref(null)
const selectedIds = ref(new Set())
const busy = ref(false)
const showDeleteConfirm = ref(false)

// The queue the user actually sees: chronological in date view, but grouped by
// species (group order, then within-group) in species view. All "next" navigation
// must index into this, not the raw date-ordered `detections`.
const orderedDetections = computed(() =>
  sort.value === 'species'
    ? speciesGroups.value.flatMap((group) => group.recordings)
    : detections.value,
)

const hasNextInQueue = computed(
  () => currentDetectionIndex.value < orderedDetections.value.length - 1,
)

// Counted from the queue itself rather than from `speciesOrder`, so the heading
// is right regardless of the sort in use or of when the grouping was last built.
const speciesCount = computed(
  () => new Set(detections.value.map((detection) => detection.species.scientific_name)).size,
)

const speciesGroups = computed(() => {
  const groupMap = new Map()
  for (const detection of detections.value) {
    const scientificName = detection.species.scientific_name
    if (!groupMap.has(scientificName)) {
      groupMap.set(scientificName, {
        scientific_name: scientificName,
        common_name: detection.species.common_name,
        image_url: detection.species.image_url,
        recordings: [],
      })
    }
    groupMap.get(scientificName).recordings.push({
      id: detection.id,
      recorded_at: detection.recorded_at,
      confidence: detection.confidence,
      clip_url: detection.clip_url,
      length_seconds: detection.length_seconds,
      validation_status: detection.validation_status,
      species: detection.species,
    })
  }
  return speciesOrder.value
    .filter((scientificName) => groupMap.has(scientificName))
    .map((scientificName) => groupMap.get(scientificName))
})

async function fetchDetections() {
  loading.value = true
  try {
    const data = await fetchDubiousDetections({ lang: lang.value })
    detections.value = data.detections
    totalCount.value = data.count
  } finally {
    loading.value = false
  }
}

function buildSpeciesOrder() {
  const countMap = new Map()
  for (const detection of detections.value) {
    const scientificName = detection.species.scientific_name
    countMap.set(scientificName, (countMap.get(scientificName) ?? 0) + 1)
  }
  speciesOrder.value = Array.from(countMap.entries())
    .sort(([, countA], [, countB]) => countB - countA)
    .map(([scientificName]) => scientificName)
}

function collapseAllSpecies() {
  collapsedSpecies.value = new Set(
    detections.value.map((detection) => detection.species.scientific_name),
  )
}

async function initializePage() {
  await fetchDetections()
  buildSpeciesOrder()
  collapseAllSpecies()
  clearSelection()
}

function toggleSelect(detectionId) {
  const next = new Set(selectedIds.value)
  if (next.has(detectionId)) next.delete(detectionId)
  else next.add(detectionId)
  selectedIds.value = next
}

function clearSelection() {
  selectedIds.value = new Set()
}

// 'none' | 'some' | 'all', driving the group header's tri-state checkbox.
function groupSelectionState(group) {
  let selectedInGroup = 0
  for (const recording of group.recordings) {
    if (selectedIds.value.has(recording.id)) selectedInGroup += 1
  }
  if (selectedInGroup === 0) return 'none'
  if (selectedInGroup === group.recordings.length) return 'all'
  return 'some'
}

function groupCheckIcon(group) {
  const state = groupSelectionState(group)
  if (state === 'all') return 'bi-check-square-fill'
  if (state === 'some') return 'bi-dash-square-fill'
  return 'bi-square'
}

function toggleGroup(group) {
  const next = new Set(selectedIds.value)
  const allSelected = group.recordings.every((recording) => next.has(recording.id))
  for (const recording of group.recordings) {
    if (allSelected) next.delete(recording.id)
    else next.add(recording.id)
  }
  selectedIds.value = next
}

async function applyBulk(action) {
  const ids = Array.from(selectedIds.value)
  if (!ids.length) return
  busy.value = true
  try {
    const processed = await bulkValidateDetections({ action, ids })
    const processedIds = new Set(processed)
    detections.value = detections.value.filter((detection) => !processedIds.has(detection.id))
    totalCount.value = detections.value.length
    clearSelection()
    refreshCount()
  } finally {
    busy.value = false
  }
}

function bulkConfirm() {
  applyBulk('confirm')
}

function askBulkDelete() {
  showDeleteConfirm.value = true
}

async function performBulkDelete() {
  await applyBulk('discard')
  showDeleteConfirm.value = false
}

function setSort(newSort) {
  buildSpeciesOrder()
  collapseAllSpecies()
  sort.value = newSort
}

function toggleSpeciesCollapse(scientificName) {
  const next = new Set(collapsedSpecies.value)
  if (next.has(scientificName)) next.delete(scientificName)
  else next.add(scientificName)
  collapsedSpecies.value = next
}

function removeDetection(detectionId) {
  detections.value = detections.value.filter((detection) => detection.id !== detectionId)
  totalCount.value = detections.value.length
}

function onValidate(recording) {
  currentDetectionIndex.value = orderedDetections.value.findIndex(
    (detection) => detection.id === recording.id,
  )
  validationModal.value.open(recording)
}

function advanceToNext(detectionId, wasValidated) {
  const savedNextIndex = currentDetectionIndex.value
  if (wasValidated) {
    justValidatedId.value = detectionId
  } else {
    justDiscardedId.value = detectionId
  }
  setTimeout(() => {
    removeDetection(detectionId)
    refreshCount()
    setTimeout(() => {
      justValidatedId.value = null
      justDiscardedId.value = null
      if (savedNextIndex < orderedDetections.value.length) {
        currentDetectionIndex.value = savedNextIndex
        validationModal.value.open(orderedDetections.value[savedNextIndex])
      }
    }, 320)
  }, 400)
}

function onSaved(detectionId) {
  advanceToNext(detectionId, true)
}

function onDiscarded(detectionId) {
  advanceToNext(detectionId, false)
}

function onSkipped() {
  const nextIndex = currentDetectionIndex.value + 1
  if (nextIndex < orderedDetections.value.length) {
    currentDetectionIndex.value = nextIndex
    setTimeout(() => {
      validationModal.value.open(orderedDetections.value[nextIndex])
    }, 300)
  }
}

// Muting or lowering a species' threshold can pull several pending detections
// out of the queue at once, so reload from the server to reflect all of them.
async function onSettingsChanged() {
  await initializePage()
  refreshCount()
}

watch(lang, initializePage)
onMounted(initializePage)
</script>

<style scoped>
.pending-bird-name {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 0.9rem;
  font-weight: 500;
}
.pending-sci-name {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 0.73rem;
}

.pending-row {
  border-bottom: 1px solid var(--limestone);
  transition: background 0.12s;
  cursor: pointer;
}
.pending-row:last-child {
  border-bottom: none;
}
.pending-row:hover {
  background: var(--lichen-pale);
}
.pending-row--validated {
  background: rgba(var(--bs-primary-rgb), 0.14) !important;
  transition: background-color 0.15s ease;
}
.pending-row--discarded {
  background: rgba(var(--bs-danger-rgb), 0.12) !important;
  transition: background-color 0.15s ease;
}
.pending-row-leave-active {
  overflow: hidden;
  max-height: 200px;
  transition:
    opacity 0.25s ease,
    max-height 0.28s ease,
    padding-top 0.28s ease,
    padding-bottom 0.28s ease;
}
.pending-row-leave-to {
  opacity: 0;
  max-height: 0 !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

.species-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 1px;
}

.species-group {
  background: var(--sheet);
  border: 1px solid var(--limestone);
  border-radius: 2px;
  overflow: hidden;
}

.species-header {
  background: none;
  border: none;
  cursor: pointer;
  transition: background 0.12s;
}
.species-header:hover {
  background: var(--lichen-pale);
}
.species-header--open {
  border-bottom: 1px solid var(--limestone);
}

.species-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 5px;
  border: 1px solid var(--limestone);
  border-radius: 1px;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--slate);
  background: var(--paper);
}

.row-check {
  background: none;
  border: none;
  padding: 2px 4px;
  font-size: 1.1rem;
  line-height: 1;
  color: var(--slate);
  cursor: pointer;
  transition: color 0.12s;
}
.row-check:hover {
  color: var(--graphite);
}
.row-check--on {
  color: rgb(var(--bs-primary-rgb));
}
.group-check {
  font-size: 1.2rem;
}

.bulk-action-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1030;
  background: var(--sheet);
  border-top: 1px solid var(--limestone);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
  padding: 12px 0 calc(12px + env(safe-area-inset-bottom));
}
.bulk-action-inner {
  display: flex;
  align-items: center;
  gap: 10px;
}
/* Clear's auto margin pushes it and the buttons after it to the right edge, so
   the count stays left on wide screens. */
.bulk-clear {
  margin-left: auto;
}
/* On phones, wrap to two lines: count + Clear on top, full-width buttons below. */
@media (max-width: 575.98px) {
  .bulk-action-inner {
    flex-wrap: wrap;
  }
  .bulk-buttons {
    order: 1;
    width: 100%;
  }
  .bulk-buttons .btn {
    flex: 1 1 0;
  }
}
.action-bar-enter-active,
.action-bar-leave-active {
  transition:
    transform 0.22s ease,
    opacity 0.22s ease;
}
.action-bar-enter-from,
.action-bar-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>
