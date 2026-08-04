<template>
  <div class="d-flex flex-wrap gap-2 gap-sm-4 mb-3 mb-sm-4">
    <div>
      <div class="text-warm-muted small mb-1 d-none d-sm-block">{{ t('filter.period') }}</div>
      <PeriodPicker
        mobile-dropdown
        :initial-selection="initialSelection"
        @change="$emit('period-change', $event)"
      />
    </div>
    <div>
      <div class="text-warm-muted small mb-1 d-none d-sm-block">{{ t('filter.sortBy') }}</div>
      <div class="btn-group btn-group-sm d-none d-sm-flex" role="group">
        <button
          v-for="opt in sortOptions"
          :key="opt.value"
          type="button"
          class="btn"
          :class="sort === opt.value ? 'btn-primary' : 'btn-outline-primary'"
          @click="$emit('update:sort', opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
      <div class="dropdown d-sm-none">
        <button
          type="button"
          class="btn btn-sm btn-outline-primary dropdown-toggle"
          data-bs-toggle="dropdown"
        >
          {{ currentSortLabel }}
        </button>
        <ul class="dropdown-menu">
          <li v-for="opt in sortOptions" :key="opt.value">
            <button
              type="button"
              class="dropdown-item"
              :class="{ active: sort === opt.value }"
              @click="$emit('update:sort', opt.value)"
            >
              {{ opt.label }}
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PeriodPicker from '../common/PeriodPicker.vue'
import { usePeriodSelection } from '../../composables/usePeriodSelection.js'

const { t } = useI18n()

const props = defineProps({
  sort: String,
})
defineEmits(['period-change', 'update:sort'])

// Restore the last chosen period (or default to 24h) and let the picker emit it
// on mount, so the species list keeps the selection across navigation/reload.
const initialSelection = usePeriodSelection().restoreSelection('24h')

const sortOptions = computed(() => [
  { value: 'most_frequent', label: t('filter.mostFrequent') },
  { value: 'most_recent', label: t('filter.mostRecent') },
  { value: 'alphabetical', label: t('filter.alphabetical') },
])

const currentSortLabel = computed(
  () => sortOptions.value.find((o) => o.value === props.sort)?.label ?? '',
)
</script>
