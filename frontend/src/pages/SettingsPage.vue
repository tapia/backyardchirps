<template>
  <div class="container pb-5">
    <h4 class="mb-4">{{ t('page.settings.title') }}</h4>

    <div v-if="initialLoading" class="text-muted small">{{ t('common.loading') }}</div>

    <template v-else>
      <div class="settings-column">
        <SettingsCard icon="bi-geo-alt" :title="t('page.settings.location')" :form="location">
          <div class="row g-3 mb-3">
            <SettingsNumberField
              class="col-sm-6"
              :form="location"
              name="location_lat"
              :label="t('page.settings.lat')"
              step="any"
            />
            <SettingsNumberField
              class="col-sm-6"
              :form="location"
              name="location_lon"
              :label="t('page.settings.lon')"
              step="any"
            />
          </div>
        </SettingsCard>

        <SettingsCard icon="bi-cloud-sun" :title="t('page.settings.weather')" :form="weather">
          <SettingsSelectField
            class="mb-4"
            :form="weather"
            name="weather_temperature_unit"
            :label="t('page.settings.weatherTemperatureUnit')"
            :options="[
              { value: 'celsius', label: t('page.settings.weatherTemperatureUnitCelsius') },
              { value: 'fahrenheit', label: t('page.settings.weatherTemperatureUnitFahrenheit') },
            ]"
          />
          <SettingsSelectField
            class="mb-4"
            :form="weather"
            name="weather_wind_speed_unit"
            :label="t('page.settings.weatherWindSpeedUnit')"
            :options="[
              { value: 'kmh', label: t('page.settings.weatherWindSpeedUnitKmh') },
              { value: 'mph', label: t('page.settings.weatherWindSpeedUnitMph') },
            ]"
          />
        </SettingsCard>

        <SettingsCard icon="bi-cpu" :title="t('page.settings.analysis')" :form="analysis">
          <SettingsSelectField
            class="mb-4"
            :form="analysis"
            name="active_acoustic_model"
            :label="t('page.settings.activeModel')"
            :hint="t('page.settings.activeModelHint')"
            :options="[
              { value: 'birdnet_3', label: t('page.settings.activeModelBirdnet3') },
              { value: 'birdnet_2', label: t('page.settings.activeModelBirdnet2') },
            ]"
          />
          <SettingsNumberField
            class="mb-3"
            :form="analysis"
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
            :form="analysis"
            name="analysis_medium_confidence"
            :label="t('page.settings.analysisMediumConfidence')"
            :hint="t('page.settings.analysisMediumConfidenceHint')"
            min="0"
            max="1"
            step="0.01"
            narrow
          />
          <SettingsNumberField
            class="mb-4"
            :form="analysis"
            name="analysis_high_confidence"
            :label="t('page.settings.analysisHighConfidence')"
            min="0"
            max="1"
            step="0.01"
            narrow
          />
        </SettingsCard>

        <SettingsCard icon="bi-hdd" :title="t('page.settings.storage')" :form="storage">
          <SettingsNumberField
            class="mb-3"
            :form="storage"
            name="clips_max_disk_usage_percent"
            :label="t('page.settings.storageMaxDiskUsage')"
            :hint="t('page.settings.storageMaxDiskUsageHint')"
            min="1"
            max="99"
            step="1"
            narrow
          />
        </SettingsCard>

        <SettingsCard icon="bi-mic" :title="t('page.settings.microphone')" :form="microphone">
          <SettingsSelectField
            class="mb-4"
            :form="microphone"
            name="audio_device"
            :label="t('page.settings.microphoneDevice')"
            :hint="t('page.settings.microphoneDeviceHint')"
            :options="microphoneOptions"
          />
        </SettingsCard>

        <SettingsCard icon="bi-key" :title="t('page.settings.credentials')" :form="credentials">
          <SettingsTextField
            class="mb-3"
            :form="credentials"
            name="telegram_token"
            type="password"
            :label="t('page.settings.telegramToken')"
            :hint="t('page.settings.telegramTokenHint')"
          />
          <SettingsTextField
            class="mb-3"
            :form="credentials"
            name="telegram_chat_id"
            :label="t('page.settings.telegramChatId')"
          />
          <SettingsTextField
            class="mb-3"
            :form="credentials"
            name="xeno_canto_api_key"
            type="password"
            :label="t('page.settings.xenoCantoApiKey')"
            :hint="t('page.settings.xenoCantoApiKeyHint')"
          />
          <SettingsTextField
            class="mb-4"
            :form="credentials"
            name="ipgeolocation_api_key"
            type="password"
            :label="t('page.settings.ipgeolocationApiKey')"
            :hint="t('page.settings.ipgeolocationApiKeyHint')"
          />
        </SettingsCard>

        <SettingsCard
          icon="bi-bell"
          :title="t('page.settings.notifications')"
          :form="notifications"
        >
          <SettingsSelectField
            class="mb-4"
            :form="notifications"
            name="notifications_language"
            :label="t('page.settings.notificationsLanguage')"
            :options="[
              { value: 'en', label: t('page.settings.notificationsLanguageEn') },
              { value: 'es', label: t('page.settings.notificationsLanguageEs') },
            ]"
          />
          <NotificationRuleField
            class="mb-3"
            :form="notifications"
            switch-id="notifPendingValidation"
            :label="t('page.settings.notificationsPendingValidation')"
            enabled-field="notifications_pending_validation_enabled"
          />
          <NotificationRuleField
            class="mb-3"
            :form="notifications"
            switch-id="notifNewSpecies"
            :label="t('page.settings.notificationsNewSpecies')"
            enabled-field="notifications_new_species_enabled"
            confidence-field="notifications_new_species_confidence"
          />
          <NotificationRuleField
            class="mb-3"
            :form="notifications"
            switch-id="notifFirstYear"
            :label="t('page.settings.notificationsFirstYear')"
            enabled-field="notifications_first_year_enabled"
            confidence-field="notifications_first_year_confidence"
          />
          <NotificationRuleField
            class="mb-3"
            :form="notifications"
            switch-id="notifFirstToday"
            :label="t('page.settings.notificationsFirstToday')"
            enabled-field="notifications_first_today_enabled"
            confidence-field="notifications_first_today_confidence"
          />
          <NotificationRuleField
            class="mb-3"
            :form="notifications"
            switch-id="notifLongAbsent"
            :label="t('page.settings.notificationsLongAbsent')"
            enabled-field="notifications_long_absent_enabled"
            confidence-field="notifications_long_absent_confidence"
            days-field="notifications_long_absent_days"
          />
          <NotificationRuleField
            class="mb-4"
            :form="notifications"
            switch-id="notifRare"
            :label="t('page.settings.notificationsRare')"
            enabled-field="notifications_rare_enabled"
            confidence-field="notifications_rare_confidence"
          />
        </SettingsCard>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchSettings, fetchAudioDevices } from '../api/index.js'
import { useSettingsForm } from '../composables/useSettingsForm.js'
import SettingsCard from '../components/settings/SettingsCard.vue'
import SettingsNumberField from '../components/settings/SettingsNumberField.vue'
import SettingsSelectField from '../components/settings/SettingsSelectField.vue'
import SettingsTextField from '../components/settings/SettingsTextField.vue'
import NotificationRuleField from '../components/settings/NotificationRuleField.vue'

const { t } = useI18n()

const initialLoading = ref(true)
const microphoneOptions = ref([])

const location = useSettingsForm({ location_lat: '', location_lon: '' })
const weather = useSettingsForm({
  weather_temperature_unit: 'celsius',
  weather_wind_speed_unit: 'kmh',
})
const analysis = useSettingsForm({
  active_acoustic_model: 'birdnet_3',
  analysis_low_confidence: '',
  analysis_medium_confidence: '',
  analysis_high_confidence: '',
})
const storage = useSettingsForm({ clips_max_disk_usage_percent: '' })
const microphone = useSettingsForm({ audio_device: '' })
const credentials = useSettingsForm({
  telegram_token: '',
  telegram_chat_id: '',
  xeno_canto_api_key: '',
  ipgeolocation_api_key: '',
})
const notifications = useSettingsForm({
  notifications_language: 'es',
  notifications_pending_validation_enabled: true,
  notifications_new_species_enabled: true,
  notifications_new_species_confidence: '0.9',
  notifications_first_year_enabled: true,
  notifications_first_year_confidence: '0.9',
  notifications_first_today_enabled: true,
  notifications_first_today_confidence: '0.9',
  notifications_long_absent_enabled: true,
  notifications_long_absent_confidence: '0.9',
  notifications_long_absent_days: '30',
  notifications_rare_enabled: true,
  notifications_rare_confidence: '0.75',
})

const settingsForms = [location, weather, analysis, storage, microphone, credentials, notifications]

onMounted(async () => {
  const [settings] = await Promise.all([fetchSettings(), loadMicrophoneOptions()])
  for (const form of settingsForms) form.load(settings)
  initialLoading.value = false
})

async function loadMicrophoneOptions() {
  // An empty value is how "no device chosen" is stored, and it means the system default.
  const options = [{ value: '', label: t('page.settings.microphoneSystemDefault') }]
  try {
    const { devices } = await fetchAudioDevices()
    for (const device of devices) options.push({ value: device.index, label: device.name })
  } catch {
    // Listening devices needs the machine's sound card. Failing here leaves the system
    // default as the only option, which is still a usable card.
  }
  microphoneOptions.value = options
}
</script>

<style scoped>
.settings-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 480px;
  margin: 0 auto;
}
</style>
