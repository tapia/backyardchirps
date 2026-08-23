<template>
  <div class="container pb-5">
    <h4 class="mb-4">{{ t('page.settings.title') }}</h4>

    <div v-if="initialLoading" class="text-muted small">{{ t('common.loading') }}</div>

    <template v-else>
      <div class="settings-column">
        <SettingsTabNav :active="activeTab" />

        <StationTab v-if="activeTab === 'station'" :form="station" />
        <RecordingTab
          v-else-if="activeTab === 'recording'"
          :form="recording"
          :microphone-options="microphoneOptions"
        />
        <DetectionTab v-else-if="activeTab === 'detection'" :form="detection" />
        <NotificationsTab v-else :form="notifications" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchSettings, fetchAudioDevices } from '../api/index.js'
import { useSettingsForm } from '../composables/useSettingsForm.js'
import { DEFAULT_SETTINGS_TAB, isSettingsTab } from '../components/settings/settingsTabs.js'
import SettingsTabNav from '../components/settings/SettingsTabNav.vue'
import StationTab from '../components/settings/StationTab.vue'
import RecordingTab from '../components/settings/RecordingTab.vue'
import DetectionTab from '../components/settings/DetectionTab.vue'
import NotificationsTab from '../components/settings/NotificationsTab.vue'

const { t } = useI18n()
const route = useRoute()

const initialLoading = ref(true)
const microphoneOptions = ref([])

// A URL naming no tab, or one that no longer exists, opens the first one rather than
// showing an empty page.
const activeTab = computed(() =>
  isSettingsTab(route.params.tab) ? route.params.tab : DEFAULT_SETTINGS_TAB,
)

// One form per tab, and they live here rather than inside the tabs, so switching tabs and
// coming back keeps whatever was typed and not saved yet.
const station = useSettingsForm({
  location_lat: '',
  location_lon: '',
  weather_temperature_unit: 'celsius',
  weather_wind_speed_unit: 'kmh',
})
const recording = useSettingsForm({
  audio_device: '',
  clips_max_disk_usage_percent: '',
})
const detection = useSettingsForm({
  active_acoustic_model: 'birdnet_3',
  analysis_low_confidence: '',
  analysis_medium_confidence: '',
  analysis_high_confidence: '',
})
const notifications = useSettingsForm({
  telegram_token: '',
  telegram_chat_id: '',
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

const settingsForms = [station, recording, detection, notifications]

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
  max-width: 640px;
  margin: 0 auto;
}
</style>
