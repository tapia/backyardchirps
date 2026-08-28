<template>
  <form class="settings-form" @submit.prevent="form.save()">
    <SettingsCard icon="bi-cpu" :title="t('page.settings.analysis')">
      <SettingsPercentField
        class="mb-3"
        :form="form"
        name="analysis_low_confidence"
        :label="t('page.settings.analysisLowConfidence')"
        :hint="t('page.settings.analysisLowConfidenceHint')"
      />
      <SettingsPercentField
        :form="form"
        name="analysis_medium_confidence"
        :label="t('page.settings.analysisMediumConfidence')"
        :hint="t('page.settings.analysisMediumConfidenceHint')"
      />
    </SettingsCard>

    <PerSpeciesRulesCard />

    <SettingsSaveBar :form="form" />
  </form>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import SettingsCard from './SettingsCard.vue'
import SettingsSaveBar from './SettingsSaveBar.vue'
import PerSpeciesRulesCard from './PerSpeciesRulesCard.vue'
import SettingsPercentField from './SettingsPercentField.vue'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()
</script>
