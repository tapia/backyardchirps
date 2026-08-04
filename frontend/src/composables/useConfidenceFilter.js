import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

// Minimum-confidence filter applied across the whole app (shared state).
const confidenceLevel = ref('high')

export function useConfidenceFilter() {
  const { t } = useI18n()

  const confidenceOptions = computed(() => [
    { value: 'low', label: t('filter.low') },
    { value: 'medium', label: t('filter.medium') },
    { value: 'high', label: t('filter.high') },
  ])

  return { confidenceLevel, confidenceOptions }
}
