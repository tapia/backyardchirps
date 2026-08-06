<template>
  <div>
    <p class="step-intro">{{ t('setup.detection.intro') }}</p>

    <SettingsNumberField
      class="mb-3"
      :form="form"
      name="analysis_low_confidence"
      :label="t('page.settings.analysisLowConfidence')"
      :hint="t('page.settings.analysisLowConfidenceHint')"
      min="0"
      max="1"
      step="0.01"
      narrow
    />
    <SettingsNumberField
      class="mb-3"
      :form="form"
      name="analysis_medium_confidence"
      :label="t('page.settings.analysisMediumConfidence')"
      :hint="t('page.settings.analysisMediumConfidenceHint')"
      min="0"
      max="1"
      step="0.01"
      narrow
    />
    <SettingsNumberField
      class="mb-3"
      :form="form"
      name="analysis_high_confidence"
      :label="t('page.settings.analysisHighConfidence')"
      min="0"
      max="1"
      step="0.01"
      narrow
    />
    <p class="field-hint">{{ t('setup.detection.defaultsAreFine') }}</p>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import SettingsNumberField from '../settings/SettingsNumberField.vue'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()
</script>
