<template>
  <div>
    <p class="step-intro">{{ t('setup.location.intro') }}</p>

    <div class="row g-3 mb-3">
      <SettingsNumberField
        class="col-sm-6"
        :form="form"
        name="location_lat"
        :label="t('page.settings.lat')"
        step="any"
      />
      <SettingsNumberField
        class="col-sm-6"
        :form="form"
        name="location_lon"
        :label="t('page.settings.lon')"
        step="any"
      />
    </div>

    <button
      v-if="geolocationAvailable"
      type="button"
      class="btn btn-outline-light btn-sm mb-3"
      :disabled="locating"
      @click="useBrowserLocation"
    >
      <span v-if="locating" class="spinner-border spinner-border-sm me-2"></span>
      <i v-else class="bi bi-crosshair me-1"></i>
      {{ t('setup.location.useBrowser') }}
    </button>

    <p v-if="locationError" class="text-warning small">{{ locationError }}</p>
    <p class="field-hint">{{ t('setup.location.why') }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsNumberField from '../settings/SettingsNumberField.vue'

const props = defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()

const geolocationAvailable = 'geolocation' in navigator
const locating = ref(false)
const locationError = ref('')

// Four decimal places is about 10 metres, which is as precise as this needs to be and
// as precise as it should be: the coordinates end up in a database that gets copied
// around, and a station's location is somebody's home.
const COORDINATE_DECIMALS = 4

function useBrowserLocation() {
  locationError.value = ''
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    (position) => {
      props.form.fields.location_lat = position.coords.latitude.toFixed(COORDINATE_DECIMALS)
      props.form.fields.location_lon = position.coords.longitude.toFixed(COORDINATE_DECIMALS)
      locating.value = false
    },
    () => {
      locationError.value = t('setup.location.browserFailed')
      locating.value = false
    },
  )
}
</script>
