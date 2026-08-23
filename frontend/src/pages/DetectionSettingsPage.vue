<template>
  <div class="container pb-5">
    <RouterLink class="back-link" to="/settings/detection">
      <i class="bi bi-chevron-left me-1"></i>{{ t('detectionSettings.backToSettings') }}
    </RouterLink>

    <h4 class="mb-1">{{ t('detectionSettings.pageTitle') }}</h4>
    <p class="text-warm-muted mb-4">{{ t('detectionSettings.pageSubtitle') }}</p>

    <div v-if="loading" class="text-warm-muted small">{{ t('common.loading') }}</div>

    <div v-else-if="species.length === 0" class="stat-card-warm text-center py-4 text-warm-muted">
      <i class="bi bi-info-circle me-1"></i>{{ t('detectionSettings.empty') }}
    </div>

    <ul v-else class="cs-list">
      <li v-for="entry in species" :key="entry.slug" class="cs-row">
        <RouterLink :to="`/species/${entry.slug}`" class="cs-main">
          <img
            :src="entry.image_url"
            :alt="entry.common_name"
            class="cs-thumb"
            @error="$event.target.style.display = 'none'"
          />
          <span class="cs-names">
            <span class="cs-common">{{ entry.common_name }}</span>
            <span class="cs-sci">{{ entry.scientific_name }}</span>
          </span>
        </RouterLink>

        <div class="cs-status">
          <span v-if="entry.blacklisted" class="cs-badge cs-badge--blacklisted">
            <i class="bi bi-eye-slash"></i>{{ t('detectionSettings.statusBlacklisted') }}
          </span>
          <span v-if="entry.auto_confirm_threshold !== null" class="cs-badge cs-badge--threshold">
            <i class="bi bi-sliders"></i
            >{{
              t('detectionSettings.statusThreshold', {
                value: `${Math.round(entry.auto_confirm_threshold * 100)}%`,
              })
            }}
          </span>
        </div>

        <button
          type="button"
          class="btn btn-outline-secondary btn-sm cs-reset"
          :disabled="resetting === entry.slug"
          @click="askReset(entry)"
        >
          <span v-if="resetting === entry.slug" class="spinner-border spinner-border-sm"></span>
          <template v-else>{{ t('detectionSettings.reset') }}</template>
        </button>
      </li>
    </ul>

    <!-- Resetting drops the species' customization, so confirm which one first:
         the rows look alike and the buttons sit close together. -->
    <ConfirmDialog
      v-if="confirming"
      :busy="resetting === confirming.slug"
      :title="t('detectionSettings.resetConfirmTitle')"
      :message="t('detectionSettings.resetConfirmMessage', { species: confirming.common_name })"
      :confirm-label="t('detectionSettings.reset')"
      @confirm="reset(confirming)"
      @cancel="confirming = null"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchCustomizedSpecies, clearSpeciesDetectionSettings } from '../api/index.js'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'

const { t } = useI18n()
const lang = inject('lang')

const species = ref([])
const loading = ref(true)
const resetting = ref(null)
// The entry awaiting confirmation, or null when no dialog is open.
const confirming = ref(null)

async function load() {
  loading.value = true
  try {
    species.value = await fetchCustomizedSpecies({ lang: lang.value })
  } finally {
    loading.value = false
  }
}

function askReset(entry) {
  confirming.value = entry
}

// Only reached once the confirmation is accepted.
async function reset(entry) {
  resetting.value = entry.slug
  try {
    await clearSpeciesDetectionSettings(entry.slug)
    species.value = species.value.filter((item) => item.slug !== entry.slug)
    confirming.value = null
  } finally {
    resetting.value = null
  }
}

watch(lang, load)
onMounted(load)
</script>

<style scoped>
.back-link {
  display: inline-block;
  font-size: 0.875rem;
  color: var(--slate);
  text-decoration: none;
  margin-bottom: 0.75rem;
}
.back-link:hover {
  color: var(--graphite);
}
.cs-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.cs-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 0.9rem;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--sheet);
}
.cs-main {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1 1 auto;
  min-width: 0;
  text-decoration: none;
  color: inherit;
}
.cs-thumb {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}
.cs-names {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.cs-common {
  font-weight: 600;
  color: var(--graphite);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cs-sci {
  font-style: italic;
  font-size: 0.82rem;
  color: var(--slate);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cs-status {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  flex-shrink: 0;
}
.cs-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.cs-badge--blacklisted {
  background: var(--paper);
  color: var(--slate);
}
.cs-badge--threshold {
  background: rgba(var(--lichen-rgb), 0.12);
  color: var(--lichen-dark);
}
.cs-reset {
  flex-shrink: 0;
}
@media (max-width: 575.98px) {
  .cs-row {
    flex-wrap: wrap;
  }
  .cs-main {
    flex: 1 1 100%;
  }
}
</style>
