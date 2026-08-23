<template>
  <form class="settings-form" @submit.prevent="form.save()">
    <SettingsCard icon="bi-cpu" :title="t('page.settings.analysis')">
      <SettingsSelectField
        class="mb-3"
        :form="form"
        name="active_acoustic_model"
        :label="t('page.settings.activeModel')"
        :hint="t('page.settings.activeModelHint')"
        :options="[
          { value: 'birdnet_3', label: t('page.settings.activeModelBirdnet3') },
          { value: 'birdnet_2', label: t('page.settings.activeModelBirdnet2') },
        ]"
      />
      <SettingsPercentField
        class="mb-3"
        :form="form"
        name="analysis_low_confidence"
        :label="t('page.settings.analysisLowConfidence')"
        :hint="t('page.settings.analysisLowConfidenceHint')"
      />
      <SettingsPercentField
        class="mb-3"
        :form="form"
        name="analysis_medium_confidence"
        :label="t('page.settings.analysisMediumConfidence')"
        :hint="t('page.settings.analysisMediumConfidenceHint')"
      />
      <SettingsPercentField
        :form="form"
        name="analysis_high_confidence"
        :label="t('page.settings.analysisHighConfidence')"
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
import SettingsSelectField from './SettingsSelectField.vue'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()
</script>
