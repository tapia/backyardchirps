<template>
  <div class="settings-card">
    <h6 class="settings-section-title">
      <i class="bi bi-sliders me-2"></i>{{ t('page.settings.perSpecies') }}
    </h6>

    <p class="settings-hint">{{ t('page.settings.perSpeciesHint') }}</p>

    <p v-if="loading" class="text-muted small mb-0">{{ t('common.loading') }}</p>

    <template v-else>
      <p class="rules-line mb-3">
        {{
          count === 0
            ? t('page.settings.perSpeciesNone')
            : t('page.settings.perSpeciesCount', count, { named: { n: count } })
        }}
      </p>
      <RouterLink class="btn btn-primary btn-sm" to="/detection-settings">
        {{ t('page.settings.perSpeciesLink') }}
      </RouterLink>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchCustomizedSpecies } from '../../api/index.js'

const { t } = useI18n()

const loading = ref(true)
const count = ref(0)

onMounted(async () => {
  try {
    const species = await fetchCustomizedSpecies()
    count.value = species.length
  } catch (error) {
    // The count is a convenience. Losing it should not hide the link to the page that
    // holds the rules themselves.
    console.error('Customized species lookup failed', error)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.rules-line {
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.85);
}
.settings-hint {
  font-size: 0.8125rem;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 1rem;
}
</style>
