<template>
  <div class="container pb-5">
    <div v-if="loading" class="text-center py-5 text-warm-muted">
      <div class="spinner-border"></div>
    </div>

    <div v-else-if="!detection" class="text-warm-muted text-center py-5">
      <i class="bi bi-slash-circle fs-1 d-block mb-3 opacity-50"></i>
      {{ t('page.recording.notFound') }}
    </div>

    <template v-else>
      <ValidationModal
        ref="validationModal"
        :has-next="false"
        @saved="onSaved"
        @discarded="onDiscarded"
      />

      <div class="species-columns mb-3">
        <img
          :src="detection.species.image_url"
          :alt="detection.species.common_name"
          class="species-thumb rounded flex-shrink-0"
          @error="$event.target.style.display = 'none'"
        />
        <div class="min-w-0">
          <div class="d-flex align-items-center gap-2">
            <RouterLink
              :to="speciesRoute(detection.species.slug)"
              class="fw-semibold text-truncate species-name"
            >
              {{ detection.species.common_name }}
            </RouterLink>
            <ConfidenceBadge class="flex-shrink-0" :confidence="detection.confidence" />
          </div>
          <div class="fst-italic text-warm-muted text-truncate species-sci">
            {{ detection.species.scientific_name }}
          </div>
          <div class="text-warm-muted species-date">
            {{ formatDateTime(detection.recorded_at) }}
          </div>
        </div>
        <button
          type="button"
          class="edit-btn ms-auto flex-shrink-0"
          v-bs-tooltip="t('modal.edit')"
          :aria-label="t('modal.edit')"
          @click="openEdit"
        >
          <i class="bi bi-pencil"></i>
        </button>
      </div>

      <SpectrogramPlayer :audio-url="detection.clip_url" />

      <div v-if="detection.reviewed_by_human || detection.original_detection" class="detail-card">
        <span v-if="detection.reviewed_by_human" class="review-badge">
          <i class="bi bi-person-check"></i>
          {{ t('page.recording.reviewedByHuman') }}
        </span>
        <div v-if="detection.original_detection" class="original-line">
          <span class="detail-label">{{ t('page.recording.originalDetection') }}</span>
          <span class="original-species">
            <RouterLink
              :to="speciesRoute(detection.original_detection.species.slug)"
              class="candidate-name"
            >
              {{ detection.original_detection.species.common_name }}
            </RouterLink>
            <ConfidenceBadge :confidence="detection.original_detection.confidence" />
          </span>
        </div>
      </div>

      <div v-if="detection.analysis_time_ms != null" class="detail-card detail-inline">
        <span class="detail-label">{{ t('page.recording.processingTime') }}</span>
        <span class="detail-value">{{ detection.analysis_time_ms }} ms</span>
      </div>

      <div v-if="detection.analysis_candidates.length" class="detail-card">
        <div class="detail-label">{{ t('page.recording.allDetections') }}</div>
        <div class="detail-hint">{{ t('page.recording.allDetectionsHint') }}</div>
        <ul class="candidate-list">
          <li
            v-for="(candidate, index) in detection.analysis_candidates"
            :key="`${candidate.label}-${index}`"
            class="candidate-row"
          >
            <RouterLink
              v-if="candidate.slug"
              :to="speciesRoute(candidate.slug)"
              class="candidate-name"
            >
              {{ candidate.common_name }}
            </RouterLink>
            <span v-else class="candidate-name candidate-name-nonbird">
              {{ candidate.label }}
              <span class="non-bird-tag">{{ t('page.recording.nonBird') }}</span>
            </span>
            <ConfidenceBadge :confidence="candidate.confidence" />
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchDetection } from '../api/index.js'
import SpectrogramPlayer from '../components/audio/SpectrogramPlayer.vue'
import ConfidenceBadge from '../components/common/ConfidenceBadge.vue'
import ValidationModal from '../components/review/ValidationModal.vue'
import { formatDateTime } from '../dates.js'
import { speciesRoute } from '../links.js'

const { t } = useI18n()
const lang = inject('lang')
const route = useRoute()
const router = useRouter()

const detection = ref(null)
const loading = ref(false)
const validationModal = ref(null)

const detectionId = computed(() => route.params.id)

function openEdit() {
  validationModal.value.open(detection.value)
}

function onSaved() {
  // A reassignment or confirmation changes the species, confidence, and review
  // status, so reload to show the current record.
  load()
}

function onDiscarded() {
  // The recording is gone, so this page would 404: leave it.
  router.push('/')
}

async function load() {
  loading.value = true
  detection.value = null
  try {
    detection.value = await fetchDetection(detectionId.value, { lang: lang.value })
  } catch {
    detection.value = null
  } finally {
    loading.value = false
  }
}

watch(detectionId, load)
onMounted(load)
</script>

<style scoped>
.species-columns {
  display: flex;
  gap: 12px;
  align-items: center;
}

.species-thumb {
  width: 88px;
  height: 88px;
  object-fit: cover;
  border-radius: 1px;
}

.species-name {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--graphite);
  line-height: 1.2;
  text-decoration: none;
}
.species-name:hover {
  color: var(--lichen);
}
.species-sci {
  font-family: 'Newsreader', Georgia, serif;
  font-style: italic;
  font-size: 0.78rem;
  margin-top: 2px;
}
.species-date {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.72rem;
}

.edit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 9px;
  font-size: 0.9rem;
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

.detail-card {
  margin-top: 16px;
  padding: 12px 14px;
  background: var(--warm-card);
  border: 1px solid var(--warm-border);
  border-radius: 3px;
  font-family: 'Source Sans 3', system-ui, sans-serif;
}
.detail-inline {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.detail-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--warm-muted);
}
.detail-value {
  font-size: 0.9rem;
  color: var(--graphite);
  font-variant-numeric: tabular-nums;
}
.detail-hint {
  font-size: 0.72rem;
  color: var(--warm-muted);
  margin: 2px 0 10px;
}
.review-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--forest);
}
.review-badge .bi {
  font-size: 0.95rem;
}
.original-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.original-species {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.candidate-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.candidate-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 0;
  border-top: 1px solid var(--warm-border);
}
.candidate-row:first-child {
  border-top: none;
}
.candidate-name {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 0.9rem;
  color: var(--graphite);
  text-decoration: none;
  min-width: 0;
}
a.candidate-name:hover {
  color: var(--lichen);
}
.candidate-name-nonbird {
  font-style: italic;
  color: var(--warm-muted);
}
.non-bird-tag {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-style: normal;
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--warm-muted);
  border: 1px solid var(--warm-border);
  border-radius: 2px;
  padding: 0 4px;
  margin-left: 6px;
}
</style>
