<template>
  <div class="d-flex flex-wrap gap-2 gap-sm-4 mb-3 mb-sm-4">
    <div>
      <div class="text-warm-muted small mb-1 d-none d-sm-block">{{ t('filter.period') }}</div>
      <PeriodPicker
        :initial-selection="initialSelection"
        @change="$emit('period-change', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import PeriodPicker from '../common/PeriodPicker.vue'
import { usePeriodSelection } from '../../composables/usePeriodSelection.js'

const { t } = useI18n()

defineEmits(['period-change'])

// Restore the last chosen period (or default to 24h) and let the picker emit it
// on mount, so the species list keeps the selection across navigation/reload.
const initialSelection = usePeriodSelection().restoreSelection('24h')
</script>
