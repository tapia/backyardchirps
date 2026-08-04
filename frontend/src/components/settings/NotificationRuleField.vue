<template>
  <div class="notification-rule">
    <div class="form-check form-switch mb-2">
      <input
        :id="switchId"
        v-model="form.fields[enabledField]"
        class="form-check-input"
        type="checkbox"
        role="switch"
        :disabled="form.loading"
      />
      <label class="form-check-label" :for="switchId">{{ label }}</label>
    </div>
    <div v-if="confidenceField && form.fields[enabledField]" class="rule-details">
      <SettingsNumberField
        :form="form"
        :name="confidenceField"
        :label="t('page.settings.notificationsMinConfidence')"
        min="0"
        max="1"
        step="0.01"
        narrow
        :class="{ 'mb-2': daysField }"
      />
      <SettingsNumberField
        v-if="daysField"
        :form="form"
        :name="daysField"
        :label="t('page.settings.notificationsAbsenceDays')"
        min="1"
        max="365"
        step="1"
        narrow
      />
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import SettingsNumberField from './SettingsNumberField.vue'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
  switchId: { type: String, required: true },
  label: { type: String, required: true },
  enabledField: { type: String, required: true },
  confidenceField: { type: String, default: '' },
  daysField: { type: String, default: '' },
})

const { t } = useI18n()
</script>

<style>
.notification-rule {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 0.75rem;
}
.notification-rule .rule-details {
  padding-left: 1.75rem;
}
</style>
