<template>
  <form class="settings-form" @submit.prevent="form.save()">
    <SettingsCard icon="bi-mic" :title="t('page.settings.microphone')">
      <SettingsSelectField
        :form="form"
        name="audio_device"
        :label="t('page.settings.microphoneDevice')"
        :hint="t('page.settings.microphoneDeviceHint')"
        :options="microphoneOptions"
      />
    </SettingsCard>

    <SettingsCard icon="bi-hdd" :title="t('page.settings.storage')">
      <SettingsNumberField
        :form="form"
        name="clips_max_disk_usage_percent"
        :label="t('page.settings.storageMaxDiskUsage')"
        :hint="t('page.settings.storageMaxDiskUsageHint')"
        min="1"
        max="99"
        step="1"
        narrow
      />
    </SettingsCard>

    <SettingsSaveBar :form="form" />
  </form>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import SettingsCard from './SettingsCard.vue'
import SettingsSaveBar from './SettingsSaveBar.vue'
import SettingsNumberField from './SettingsNumberField.vue'
import SettingsSelectField from './SettingsSelectField.vue'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
  microphoneOptions: { type: Array, required: true },
})

const { t } = useI18n()
</script>
