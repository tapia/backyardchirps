<template>
  <Teleport to="body">
    <div v-if="visible" class="validate-backdrop"></div>
    <div class="modal fade validate-modal" ref="modalEl" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered validate-dialog">
        <div class="modal-content">
          <div v-if="detection" class="modal-body" :class="{ 'modal-body--staff': isStaff }">
            <!-- Actions: share + close, own row so they never compete with the name for space -->
            <div class="modal-actions">
              <ShareRecordingButton :recording-id="detection.id" copied-label-side="start" />
              <button
                v-if="isStaff"
                type="button"
                class="modal-close-btn"
                @click="openDetectionSettings"
                :disabled="saving"
                :aria-label="t('detectionSettings.dialogAdminTitle')"
                v-bs-tooltip="t('detectionSettings.dialogAdminTitle')"
              >
                <i class="bi bi-sliders"></i>
              </button>
              <button
                type="button"
                class="modal-close-btn"
                @click="close"
                :disabled="saving"
                :aria-label="t('common.close')"
                v-bs-tooltip="t('common.close')"
              >
                <i class="bi bi-x-lg"></i>
              </button>
            </div>

            <!-- Species header: image + names -->
            <div
              class="species-block"
              :class="{
                'species-block--flash': headerFlashing,
                'species-block--reassigned': isReassigned,
              }"
            >
              <button
                v-if="isReassigned"
                class="species-revert"
                @click="resetToOriginalSpecies"
                :aria-label="t('modal.validateCancelChange')"
                v-bs-tooltip="t('modal.validateCancelChange')"
              >
                <i class="bi bi-clock-history"></i>
              </button>
              <div class="species-columns">
                <img
                  :src="selectedSpecies.image_url"
                  :alt="selectedSpecies.common_name"
                  class="species-thumb"
                  @error="$event.target.style.display = 'none'"
                />
                <div class="min-w-0">
                  <div class="fw-semibold text-truncate species-name">
                    {{ selectedSpecies.common_name }}
                  </div>
                  <div class="fst-italic text-warm-muted text-truncate species-sci">
                    {{ selectedSpecies.scientific_name }}
                  </div>
                  <!-- While a change is pending the date and score describe the
                       identification being replaced, not the one now named
                       above, so they move into a "before" chip rather than
                       sitting under the new species as if they were its own. -->
                  <div v-if="!isReassigned" class="species-date">
                    <span class="species-date__text text-warm-muted">
                      <i class="bi bi-calendar3"></i>{{ formatDateTime(detection.recorded_at) }}
                    </span>
                    <ConfidenceBadge class="flex-shrink-0" :confidence="detection.confidence" />
                  </div>
                  <div v-else class="species-chips">
                    <span class="species-chip species-chip--pending">
                      {{ t('modal.validatePendingChange') }}
                    </span>
                    <span class="species-chip">
                      {{
                        t('modal.validateBefore', {
                          species: detection.species.common_name,
                          confidence: formatPercent(detection.confidence),
                        })
                      }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- The question frames the dialog rather than sitting in a panel
                 partway down it: read what is being asked, listen, then answer
                 with the controls below. -->
            <div class="prompt-header">
              <div class="prompt-title">{{ t('modal.validatePromptTitle') }}</div>
              <div class="prompt-subtitle">{{ t('modal.validatePromptSubtitle') }}</div>
            </div>

            <div class="spectro-card">
              <SpectrogramPlayer ref="spectrogramPlayer" :audio-url="detection.clip_url" />
            </div>

            <!-- Only when the recording holds more than one bird. The species
                 under review is named in the header and in the question, so the
                 list is purely what else the recording already accounts for. -->
            <IdentifiedSpeciesList v-if="alsoIdentified.length" :species="alsoIdentified" />

            <div class="answer-block">
              <!-- A staged change replaces the search: the question is no longer
                   "which species" but "keep this change or drop it", and the
                   answer is spelled out rather than left to the header. -->
              <div v-if="isReassigned" class="pending-change">
                <div class="stat-label mb-2">{{ t('modal.validateNewSpecies') }}</div>
                <div class="pending-change__row">
                  <i class="bi bi-feather pending-change__icon"></i>
                  <span class="pending-change__name text-truncate">
                    {{ selectedSpecies.common_name }}
                  </span>
                  <span class="pending-change__note">
                    {{
                      t('modal.validateReplacesSpecies', {
                        species: detection.species.common_name,
                      })
                    }}
                  </span>
                </div>
                <div v-if="alsoIdentified.length" class="kept-note">
                  <i class="bi bi-check-circle kept-note__icon"></i>
                  <span>{{ t('modal.validateOthersKept', { others: otherSpeciesNames }) }}</span>
                </div>
              </div>

              <!-- Desktop: reassign search (always visible) + reference dropdown -->
              <div v-else-if="!isMobile" class="validate-columns">
                <div class="reassign-col">
                  <div class="stat-label mb-2">{{ t('modal.validateReassign') }}</div>
                  <SpeciesSearchPicker
                    ref="speciesPicker"
                    small
                    floating
                    drop-up
                    :list-height="220"
                    :selected-scientific-name="selectedSpecies.scientific_name"
                    :unavailable-scientific-names="unavailableScientificNames"
                    :unavailable-label="t('modal.validateUnavailable')"
                    :unavailable-reason="t('modal.validateAlreadyIdentified')"
                    @select="selectSpecies"
                  />
                </div>

                <div class="reference-col">
                  <!-- Spacer matching the "Reasignar especie" label so the toggle
                       lines up with the search field, not the label above it. -->
                  <div class="stat-label mb-2 ref-calls-spacer" aria-hidden="true">&nbsp;</div>
                  <ReferenceCallsDropdown
                    ref="referenceDropdown"
                    drop-up
                    :sounds="referenceSounds"
                    :loading="referenceSoundsLoading"
                  />
                </div>
              </div>

              <!-- Mobile: two collapsed rows, each opening a full-height sheet.
                   The dialog itself never expands to show results inline. -->
              <div v-else class="mobile-rows">
                <button class="mobile-row" @click="openMobileSheet('reassign')">
                  <span class="mobile-row__label">
                    <i class="bi bi-search"></i>{{ t('modal.validateReassign') }}
                  </span>
                  <i class="bi bi-chevron-down"></i>
                </button>
                <button class="mobile-row" @click="openMobileSheet('reference')">
                  <span class="mobile-row__label">
                    <i class="bi bi-soundwave"></i>{{ t('modal.validateReferenceCalls') }}
                  </span>
                  <i class="bi bi-chevron-down"></i>
                </button>
              </div>
            </div>
          </div>

          <div class="modal-footer border-0 validate-footer">
            <button
              class="btn btn-outline-danger discard-btn"
              @click="askDiscard"
              :disabled="saving"
            >
              <i class="bi bi-trash3 me-1"></i>{{ discardLabel }}
            </button>
            <div class="validate-footer__end">
              <!-- With a change staged, dropping it is the useful escape rather
                   than moving on and leaving it half-made. -->
              <button
                v-if="isReassigned"
                class="skip-btn"
                @click="resetToOriginalSpecies"
                :disabled="saving"
              >
                {{ t('modal.validateCancelChange') }}
              </button>
              <button v-else class="skip-btn" @click="onSkip" :disabled="saving || !hasNext">
                {{ t('modal.validateSkip') }}
              </button>
              <button class="btn btn-primary save-btn" @click="onSave" :disabled="saving">
                <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-check-lg me-1"></i>
                {{ isReassigned ? t('modal.validateSaveChange') : t('modal.validateConfirm') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Mobile task sheets: opened from the collapsed rows, closed back to the
         dialog. The picker/list content is the same used on desktop. -->
    <SlidePanel
      v-if="isMobile && mobileSheet === 'reassign'"
      :title="t('modal.validateReassign')"
      @close="closeMobileSheet"
    >
      <div class="reassign-sheet">
        <SpeciesSearchPicker
          ref="mobileSpeciesPicker"
          small
          :selected-scientific-name="selectedSpecies.scientific_name"
          :unavailable-scientific-names="unavailableScientificNames"
          :unavailable-label="t('modal.validateUnavailable')"
          :unavailable-reason="t('modal.validateAlreadyIdentified')"
          @select="selectSpecies"
        />
      </div>
    </SlidePanel>

    <SlidePanel
      v-else-if="isMobile && mobileSheet === 'reference'"
      :title="t('modal.validateReferenceCalls')"
      @close="closeMobileSheet"
    >
      <div class="reference-sheet">
        <div v-if="referenceSoundsLoading" class="text-center text-warm-muted py-4">
          <div class="spinner-border spinner-border-sm"></div>
        </div>
        <ReferenceCallList v-else ref="mobileSoundsPlayer" :sounds="referenceSounds" />
      </div>
    </SlidePanel>

    <!-- Deleting is irreversible, so it goes through a confirmation. Sits on top
         of the dialog and of any open sheet, and is dismissed first by Escape
         and by the Back button. -->
    <ConfirmDialog
      v-if="confirmingDiscard"
      danger
      :self-dismiss="false"
      :busy="saving"
      :title="t('modal.validateDiscardConfirmTitle', { species: detection.species.common_name })"
      :message="
        alsoIdentified.length
          ? t('modal.validateDiscardReviewOutcome')
          : t('modal.validateDiscardConfirmMessage')
      "
      :confirm-label="
        t('modal.validateDiscardConfirmAccept', { species: detection.species.common_name })
      "
      @confirm="onDiscard"
      @cancel="cancelDiscard"
    >
      <!-- Only when the recording holds more than one bird, where deleting one
           identification must not read as deleting the lot. With a single bird
           there is nothing to contrast, and the title and button already name
           what goes. -->
      <ul v-if="alsoIdentified.length" class="outcome-list">
        <li class="outcome">
          <i class="bi bi-x-circle outcome__icon outcome__icon--removed"></i>
          <div class="min-w-0">
            <div class="outcome__label">{{ t('modal.validateOutcomeRemoved') }}</div>
            <div class="outcome__species">{{ detection.species.common_name }}</div>
          </div>
        </li>
        <li v-for="species in alsoIdentified" :key="species.scientific_name" class="outcome">
          <i class="bi bi-check-circle outcome__icon outcome__icon--kept"></i>
          <div class="min-w-0">
            <div class="outcome__label">{{ t('modal.validateOutcomeKept') }}</div>
            <div class="outcome__species">{{ species.common_name }}</div>
          </div>
        </li>
      </ul>
    </ConfirmDialog>

    <SpeciesDetectionSettingsModal
      v-if="detection"
      ref="detectionSettingsModal"
      :species-slug="detection.species.slug"
      :common-name="detection.species.common_name"
      :back-button-close="false"
      @updated="onDetectionSettingsUpdated"
    />
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, inject, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal } from 'bootstrap'
import * as api from '../../api/index.js'
import { formatDateTime } from '../../dates.js'
import ConfidenceBadge from '../common/ConfidenceBadge.vue'
import SpectrogramPlayer from '../audio/SpectrogramPlayer.vue'
import SpeciesSearchPicker from '../species/SpeciesSearchPicker.vue'
import ReferenceCallsDropdown from '../recordings/ReferenceCallsDropdown.vue'
import ReferenceCallList from '../recordings/ReferenceCallList.vue'
import SlidePanel from '../common/SlidePanel.vue'
import ConfirmDialog from '../common/ConfirmDialog.vue'
import IdentifiedSpeciesList from './IdentifiedSpeciesList.vue'
import { useMediaQuery } from '../../composables/useMediaQuery.js'
import { useHistoryLayers } from '../../composables/useHistoryLayers.js'
import ShareRecordingButton from '../recordings/ShareRecordingButton.vue'
import { useAuth } from '../../composables/useAuth.js'
import SpeciesDetectionSettingsModal from '../species/SpeciesDetectionSettingsModal.vue'

const { t } = useI18n()
const lang = inject('lang')
const { currentUser } = useAuth()

const props = defineProps({
  hasNext: { type: Boolean, default: true },
})

const emit = defineEmits(['saved', 'discarded', 'skipped', 'changed'])

// Admin-only detection settings for the current species (blacklist / threshold),
// edited through the shared settings dialog.
const isStaff = computed(() => Boolean(currentUser.value?.is_staff))
const detectionSettingsModal = ref(null)

const modalEl = ref(null)
const visible = ref(false)
const detection = ref(null)
const selectedSpecies = ref(null)
const speciesPicker = ref(null)
const saving = ref(false)
const headerFlashing = ref(false)
const isResetting = ref(false)
const referenceSounds = ref([])
const referenceSoundsLoading = ref(false)
const referenceDropdown = ref(null)
const spectrogramPlayer = ref(null)

// Mobile: the reassign/reference panels become full-height sheets opened one at
// a time from collapsed rows. `mobileSheet` is null | 'reassign' | 'reference'.
const isMobile = useMediaQuery('(max-width: 575.98px)')
const mobileSheet = ref(null)
const mobileSpeciesPicker = ref(null)
const mobileSoundsPlayer = ref(null)

// The delete confirmation is the topmost layer whenever it is open.
const confirmingDiscard = ref(false)

let bsModal = null

// Back closes the topmost layer: the delete confirmation, then an open mobile sheet,
// then the dialog itself. Each layer pushes one history entry when it opens and hands
// back that entry when it closes, whichever way it was closed.
const historyLayers = useHistoryLayers()

function dismissMobileSheet() {
  mobileSoundsPlayer.value?.reset()
  mobileSheet.value = null
}

function dismissDiscardConfirmation() {
  confirmingDiscard.value = false
}

// Switching to the desktop layout unmounts the sheets, so close any open one.
watch(isMobile, (mobile) => {
  if (!mobile && mobileSheet.value) closeMobileSheet()
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown, true)
})

const isReassigned = computed(
  () =>
    selectedSpecies.value &&
    detection.value &&
    selectedSpecies.value.scientific_name !== detection.value.species.scientific_name,
)

// The other species this recording already holds. Empty for the ordinary case
// of one bird per recording, which hides the list and its notes entirely.
const alsoIdentified = computed(() => detection.value?.also_identified ?? [])

const otherSpeciesNames = computed(() =>
  alsoIdentified.value.map((species) => species.common_name).join(', '),
)

// Reassigning onto a species the recording already holds would identify one
// bird twice, so those stay listed in the search but cannot be chosen. The
// species under review is excluded: picking it again is just cancelling.
const unavailableScientificNames = computed(() =>
  alsoIdentified.value.map((species) => species.scientific_name),
)

// Naming the species answers "delete what?" when the recording holds several.
// A phone has no room for it beside the other two actions, and the question is
// answered anyway by the confirmation, which names the species and everything
// the recording keeps before anything is removed.
const discardLabel = computed(() =>
  alsoIdentified.value.length && !isMobile.value
    ? t('modal.validateDiscardSpecies', { species: detection.value.species.common_name })
    : t('modal.validateDiscard'),
)

watch(
  () => selectedSpecies.value?.scientific_name,
  (newVal, oldVal) => {
    if (isResetting.value || !newVal || !oldVal || newVal === oldVal) return
    headerFlashing.value = false
    nextTick(() => {
      headerFlashing.value = true
      setTimeout(() => {
        headerFlashing.value = false
      }, 700)
    })
  },
)

watch(
  () => selectedSpecies.value?.slug,
  async (slug) => {
    if (!slug) {
      referenceSounds.value = []
      return
    }
    referenceSoundsLoading.value = true
    try {
      const species = await api.fetchSpeciesDetail(slug, { lang: lang.value })
      referenceSounds.value = species.sounds ?? []
    } catch {
      referenceSounds.value = []
    } finally {
      referenceSoundsLoading.value = false
    }
  },
)

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.stopImmediatePropagation()
    // Escape dismisses the topmost layer: the confirmation, then an open sheet,
    // else the modal.
    if (confirmingDiscard.value) {
      cancelDiscard()
    } else if (mobileSheet.value) {
      closeMobileSheet()
    } else {
      close()
    }
  }
}

// The row the queue already has renders the dialog immediately; the rest of the
// recording only the dialog needs (`also_identified`) comes from the detail
// endpoint right after, so the queue never has to carry it.
let detailRequest = 0

async function loadDetail(detectionId) {
  const requestId = ++detailRequest
  try {
    const detail = await api.fetchDetection(detectionId, { lang: lang.value })
    // Skipping quickly can land an earlier response after a later one.
    if (requestId === detailRequest) detection.value = detail
  } catch {
    // Keep the row we opened with: everything but the sibling species is in it.
  }
}

function open(detectionData) {
  isResetting.value = true
  detection.value = detectionData
  loadDetail(detectionData.id)
  selectedSpecies.value = { ...detectionData.species }
  speciesPicker.value?.clear()
  saving.value = false
  referenceDropdown.value?.close()
  mobileSheet.value = null
  confirmingDiscard.value = false
  visible.value = true
  nextTick(() => {
    isResetting.value = false
  })

  // focus: false disables Bootstrap's focus trap. Without this it steals focus
  // back from the mobile sheets (teleported outside .modal), so their inputs
  // could never be tapped/typed into.
  if (!bsModal)
    bsModal = new Modal(modalEl.value, { keyboard: false, backdrop: false, focus: false })
  bsModal.show()

  document.removeEventListener('keydown', onKeydown, true)
  document.addEventListener('keydown', onKeydown, true)
  historyLayers.start()
  // Skipping to the next detection reuses the open dialog, which must not push a
  // second entry for the same layer.
  if (historyLayers.depth() === 0) historyLayers.push(close)
}

function close() {
  document.removeEventListener('keydown', onKeydown, true)
  // Stop listening before giving the entries back, so our own handler does not run
  // on the way out.
  historyLayers.stop()
  speciesPicker.value?.clear()
  spectrogramPlayer.value?.stop()
  referenceDropdown.value?.close()
  mobileSoundsPlayer.value?.reset()
  referenceSounds.value = []

  historyLayers.clear()
  confirmingDiscard.value = false
  mobileSheet.value = null
  visible.value = false
  bsModal?.hide()
}

function openMobileSheet(name) {
  spectrogramPlayer.value?.stop()
  mobileSheet.value = name
  historyLayers.push(dismissMobileSheet)
  if (name === 'reassign') {
    nextTick(() => mobileSpeciesPicker.value?.focus())
  }
}

function closeMobileSheet() {
  if (!mobileSheet.value) return
  dismissMobileSheet()
  historyLayers.pop()
}

function selectSpecies(species) {
  selectedSpecies.value = { ...species }
  speciesPicker.value?.clear()
  mobileSpeciesPicker.value?.clear()
  // On mobile, picking a species returns to the dialog; no-op on desktop.
  closeMobileSheet()
}

// Matches ConfidenceBadge, so the score in the "before" chip reads the same as
// it did in the badge it replaces.
function formatPercent(confidence) {
  return `${(confidence * 100).toFixed(0)}%`
}

function resetToOriginalSpecies() {
  isResetting.value = true
  selectSpecies(detection.value.species)
  nextTick(() => {
    isResetting.value = false
  })
}

function onSkip() {
  emit('skipped')
  close()
}

async function onSave() {
  saving.value = true
  try {
    const payload = {}
    if (selectedSpecies.value.scientific_name !== detection.value.species.scientific_name) {
      payload.species_scientific_name = selectedSpecies.value.scientific_name
    }
    await api.validateDetection(detection.value.id, payload)
    emit('saved', detection.value.id)
    close()
  } finally {
    saving.value = false
  }
}

function askDiscard() {
  spectrogramPlayer.value?.stop()
  confirmingDiscard.value = true
  historyLayers.push(dismissDiscardConfirmation)
}

function cancelDiscard() {
  if (!confirmingDiscard.value) return
  dismissDiscardConfirmation()
  historyLayers.pop()
}

// Only reached once the confirmation is accepted. close() gives back the
// confirmation's history entry along with the dialog's own.
async function onDiscard() {
  saving.value = true
  try {
    await api.discardDetection(detection.value.id)
    emit('discarded', detection.value.id)
    close()
  } finally {
    saving.value = false
  }
}

// Close this dialog before opening the shared settings modal: stacking the two
// would fight over the Escape key and the Back button, and a blacklist/threshold
// change usually pulls the current detection out of the queue anyway.
async function openDetectionSettings() {
  const settings = await api.fetchSpeciesDetectionSettings(detection.value.species.slug)
  detectionSettingsModal.value?.open(settings)
  close()
}

// Muting or changing the threshold can pull several detections out of the
// queue, so tell the page to reload.
function onDetectionSettingsUpdated() {
  emit('changed')
}

defineExpose({ open })
</script>

<style scoped>
.validate-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1060;
}
.validate-modal {
  z-index: 1065;
}
.validate-dialog {
  max-width: 680px;
}

.modal-content {
  border-radius: 16px;
}
.modal-body {
  position: relative;
  padding: var(--body-padding-top) var(--body-padding-x) 8px;

  /* The actions column is absolutely positioned over the species header, so its
     footprint has to be reserved by the elements underneath it. Everything that
     has to dodge it derives its edge from these, rather than repeating the
     arithmetic as literals that drift apart. */
  --body-padding-x: 22px;
  --body-padding-top: 20px;
  --actions-inset: 18px;
  --actions-top: 14px;
  --actions-size: 34px;
  --actions-gap: 8px;
  /* Share + close, plus the settings button for staff. */
  --actions-count: 2;
  --actions-height: calc(
    var(--actions-count) * var(--actions-size) + (var(--actions-count) - 1) * var(--actions-gap)
  );
}
.modal-body--staff {
  --actions-count: 3;
}

/* Mobile: a sheet bounded by the visible viewport instead of one that grows
   past it. The content scrolls; the footer stays pinned. Every vertical size
   below is derived from the viewport, so the layout adapts to any screen
   height rather than to particular devices. */
@media (max-width: 575.98px) {
  .validate-modal {
    height: 100dvh;
    overflow: hidden;
  }
  .validate-modal .modal-dialog {
    margin: 0;
    max-width: 100%;
    height: 100dvh;
  }
  .validate-modal .modal-content {
    border-radius: 0;
    height: 100%;
    max-height: 100dvh;
    display: flex;
    flex-direction: column;
  }
  .validate-modal .modal-body {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    /* Vertical rhythm shrinks on shorter screens without dropping anything.
       Padding comes from the base rule, which reads these back. */
    --stack-gap: clamp(8px, 2.2dvh, 8px);
    --body-padding-top: clamp(12px, 2.5dvh, 20px);
  }
  .validate-modal .spectro-card,
  .validate-modal .prompt-header,
  .validate-modal .answer-block {
    margin-top: var(--stack-gap);
  }
  /* The spectrogram is the one element that can give back height gracefully:
     it scales instead of losing information. Capping the wrapper's width rather
     than the canvas' height keeps the shape fixed while it shrinks, since the
     canvas derives its height from its width. */
  .spectro-card :deep(.spectrogram-player) {
    max-width: min(100%, calc(clamp(96px, 17dvh, 240px) * var(--spectrogram-ratio)));
  }
}

/* ── Top actions: circular share + close ─────────────────────── */
/* Tucked into the top-right corner (overlapping the header) so they don't take
   a full row of vertical space. Stacked vertically (share below close) to claim
   a narrow column; `.species-block` stops short of that column so nothing is
   ever drawn underneath it. */
.modal-actions {
  position: absolute;
  top: var(--actions-top);
  right: var(--actions-inset);
  z-index: 3;
  display: flex;
  flex-direction: column-reverse;
  align-items: center;
  gap: var(--actions-gap);
}
.modal-close-btn,
.modal-actions :deep(.share-btn) {
  width: var(--actions-size);
  height: var(--actions-size);
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-soft);
  background: var(--sheet);
  color: var(--slate);
  font-size: 0.95rem;
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s,
    border-color 0.12s;
}
.modal-close-btn:hover,
.modal-actions :deep(.share-btn):hover {
  background: var(--paper);
  border-color: var(--dust);
  color: var(--graphite);
}
.modal-close-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

/* ── Species header ──────────────────────────────────────────── */
.species-thumb {
  width: 88px;
  height: 88px;
  object-fit: cover;
  flex-shrink: 0;
  border-radius: 14px;
}

.species-columns {
  display: flex;
  gap: 14px;
  align-items: center;
}

/* Undo control for a staged change, sitting where the header's own actions are
   rather than below the name, so it does not compete with the two chips. */
.species-revert {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--lichen);
  border: 1px solid var(--lichen);
  font-size: 0.95rem;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}
.species-revert:hover {
  background: var(--lichen);
  color: var(--sheet);
}

.species-name {
  min-width: 0;
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--graphite);
  line-height: 1.2;
}
.species-sci {
  font-family: 'Newsreader', Georgia, serif;
  font-style: italic;
  font-size: 0.92rem;
  margin-top: 2px;
}
.species-date {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.8rem;
  line-height: 1;
  margin-top: 4px;
}
.species-date__text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  line-height: 1;
}
/* The badge ships with line-height 1.5, which makes its box taller than the
   date text and reads as misaligned even when centered. Match it to the text. */
.species-date :deep(.confidence-badge) {
  line-height: 1;
  padding-top: 3px;
  padding-bottom: 3px;
  margin-bottom: 3px;
}

@keyframes species-flash {
  0% {
    background-color: rgba(var(--bs-primary-rgb), 0.3);
  }
  100% {
    background-color: rgba(var(--bs-primary-rgb), 0);
  }
}
.species-block {
  position: relative;
  border: 1.5px solid transparent;
  border-radius: 16px;
  padding: 10px;
  /* Left edge sits on the body's content edge, so the reassigned border and its
     lichen bar line up with the cards below instead of hanging left of them.
     Right edge stops one gap short of the actions column: once reassigned paints
     a background, anything past this point would sit under the buttons. */
  margin-right: calc(
    var(--actions-inset) + var(--actions-size) + var(--actions-gap) - var(--body-padding-x)
  );
  /* The block is the only thing meant to sit beside the actions column, so it
     has to be at least as tall as the column is. A short thumbnail would
     otherwise end above the last button and let the spectrogram slide under it. */
  min-height: calc(var(--actions-top) + var(--actions-height) - var(--body-padding-top));
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}
.species-block--flash {
  animation: species-flash 1s ease-out;
}
.species-block--reassigned {
  background-color: var(--lichen-pale);
  border-color: rgba(var(--lichen-rgb), 0.4);
  box-shadow: inset 3px 0 0 var(--lichen);
}
/* Only the reassigned state shows the revert control, so only it reserves that
   slot on the right; the name keeps its full width otherwise. */
.species-block--reassigned .species-columns {
  padding-right: 44px;
}

/* "Pending change" and what it replaces, in place of the date and score, which
   belong to the identification being replaced rather than the new one. */
.species-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.species-chip {
  display: inline-flex;
  align-items: center;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.78rem;
  color: var(--graphite);
  background: var(--paper);
  border: 1px solid var(--limestone);
  padding: 4px 12px;
  border-radius: 999px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.species-chip--pending {
  font-weight: 600;
  color: var(--sheet);
  background: var(--lichen);
  border-color: var(--lichen);
}

/* ── Spectrogram card ────────────────────────────────────────── */
/* Placement only. The card itself (border, background, control padding) is
   SpectrogramPlayer's own look, shared with every other place it appears. */
.spectro-card {
  margin-top: 16px;
}

/* Outcome rows inside the delete confirmation: what goes, what stays. Carries
   its own rule and spacing, so a recording with one bird shows neither. */
.outcome-list {
  list-style: none;
  margin: 14px 0 0;
  padding: 12px 0 0;
  border-top: 1px solid var(--border-soft);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.outcome {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.outcome__icon {
  flex-shrink: 0;
  margin-top: 2px;
  font-size: 1rem;
}
.outcome__icon--removed {
  color: var(--bs-danger);
}
.outcome__icon--kept {
  color: var(--lichen);
}
.outcome__label {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.78rem;
  color: var(--slate);
}
.outcome__species {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1rem;
  color: var(--graphite);
}

/* The staged change, standing in for the search once one is made. */
.pending-change__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--sheet);
}
.pending-change__icon {
  flex-shrink: 0;
  color: var(--slate);
}
.pending-change__name {
  min-width: 0;
  font-family: 'Newsreader', Georgia, serif;
  font-size: 0.95rem;
  color: var(--graphite);
}
.pending-change__note {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 0.78rem;
  color: var(--warm-muted);
}
.kept-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(var(--lichen-rgb), 0.12);
  font-size: 0.8rem;
  color: var(--slate);
}
.kept-note__icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--lichen);
}

@media (max-width: 575.98px) {
  .pending-change__row {
    flex-wrap: wrap;
  }
  .pending-change__note {
    margin-left: 0;
    width: 100%;
  }
}

/* ── The question ────────────────────────────────────────────── */
/* Sits directly under the species and above the audio, unboxed, so the dialog
   reads as one question rather than a stack of panels. */
.prompt-header {
  margin-top: 12px;
}
.answer-block {
  margin-top: 16px;
}
.prompt-title {
  font-family: 'Newsreader', Georgia, serif;
  font-size: 1rem;
  font-weight: 600;
  color: var(--graphite);
  line-height: 1.2;
}
.prompt-subtitle {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.8rem;
  color: var(--slate);
  margin-top: 2px;
}

/* ── Reassign + reference columns ────────────────────────────── */
/* Spacing above these comes from the prompt card's own gap, since they now sit
   inside it. */
.validate-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}

/* ── Reassign search field ───────────────────────────────────── */
/* Align the shared SpeciesSearchPicker with the reference-calls toggle:
   same rounded corners, border colour and height so they read as siblings. */
.reassign-col :deep(.search-input) {
  height: 44px;
  border-radius: 12px;
  border-color: var(--dust);
  font-size: 0.85rem;
  background-color: #fff;
}
.reassign-col :deep(.species-list) {
  border-radius: 12px;
  border-color: var(--dust);
}

/* ── Mobile: collapsed rows + full-height task sheets ────────── */
.mobile-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.mobile-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 10px;
  height: 48px;
  background: var(--sheet);
  border: 1px solid var(--dust);
  border-radius: 12px;
  padding: 0 14px;
  cursor: pointer;
  color: var(--graphite);
  transition:
    background 0.12s,
    border-color 0.12s;
}
.mobile-row:hover {
  background: var(--lichen-pale);
  border-color: var(--lichen);
}
.mobile-row__label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
}
.mobile-row__label .bi {
  color: var(--lichen);
  font-size: 1rem;
}
.mobile-row > .bi-chevron-down {
  color: var(--slate);
}

/* Reassign sheet: fixed search field at the top, results fill and scroll. */
.reassign-sheet {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.reassign-sheet :deep(.search-picker) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.reassign-sheet :deep(.search-input) {
  border-radius: 10px;
  background-color: #fff;
}
.reassign-sheet :deep(.species-list) {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none !important;
  margin-top: 12px;
  border: none;
}

/* Reference sheet: let the list sit flush inside the scrolling sheet body. */
.reference-sheet :deep(.stat-card-warm) {
  border: none;
  border-radius: 0;
  background: transparent;
}
.reference-sheet :deep(.rec-list) {
  margin-top: 0;
  border-top: none;
}

/* ── Footer ──────────────────────────────────────────────────── */
.validate-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: nowrap;
  padding: 16px 22px 20px;
}
.validate-footer__end {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}
.discard-btn,
.save-btn {
  font-weight: 600;
  padding: 8px 18px;
  border-radius: 8px;
}
/* The delete button is the only one whose label varies in length, so it is the
   one that gives way: an unusually long species name is clipped rather than
   pushing the actions that end the review off the dialog. */
.discard-btn {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.skip-btn {
  border: none;
  background: none;
  padding: 4px 6px;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--lichen);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
  transition: color 0.12s;
}
.skip-btn:hover {
  color: var(--lichen-dark);
}
.skip-btn:disabled {
  color: var(--dust);
  text-decoration: none;
  cursor: default;
}

@media (max-width: 575.98px) {
  .species-thumb {
    width: 72px;
    height: 72px;
    border-radius: 12px;
  }
  .species-name {
    font-size: 1.05rem;
  }
  .species-sci {
    font-size: 0.85rem;
  }
  /* Pinned below the scrolling body: never scrolls away, and clears the home
     indicator / gesture bar via the bottom safe-area inset. All three actions
     share one row, which is why the delete button drops the species name at
     this width (see discardLabel). */
  .validate-footer {
    flex: 0 0 auto;
    gap: 8px;
    border-top: 1px solid var(--border-soft);
    padding: clamp(8px, 1.6dvh, 16px) 16px;
    padding-bottom: calc(clamp(8px, 1.6dvh, 16px) + env(safe-area-inset-bottom));
  }
  .validate-footer__end {
    gap: 8px;
  }
  .discard-btn,
  .save-btn {
    padding: 8px 14px;
    white-space: nowrap;
  }
}
</style>
