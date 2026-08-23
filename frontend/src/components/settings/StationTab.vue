<template>
  <form class="settings-form" @submit.prevent="form.save()">
    <SettingsCard icon="bi-geo-alt" :title="t('page.settings.location')">
      <LocationMapPicker
        class="mb-3"
        :latitude="form.fields.location_lat"
        :longitude="form.fields.location_lon"
        @place="place"
      />
      <div class="row g-3">
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
    </SettingsCard>

    <RegionPackCard :latitude="form.fields.location_lat" :longitude="form.fields.location_lon" />

    <SettingsCard icon="bi-cloud-sun" :title="t('page.settings.weather')">
      <SettingsSelectField
        class="mb-3"
        :form="form"
        name="weather_temperature_unit"
        :label="t('page.settings.weatherTemperatureUnit')"
        :options="[
          { value: 'celsius', label: t('page.settings.weatherTemperatureUnitCelsius') },
          { value: 'fahrenheit', label: t('page.settings.weatherTemperatureUnitFahrenheit') },
        ]"
      />
      <SettingsSelectField
        :form="form"
        name="weather_wind_speed_unit"
        :label="t('page.settings.weatherWindSpeedUnit')"
        :options="[
          { value: 'kmh', label: t('page.settings.weatherWindSpeedUnitKmh') },
          { value: 'mph', label: t('page.settings.weatherWindSpeedUnitMph') },
        ]"
      />
    </SettingsCard>

    <SettingsSaveBar :form="form" />
  </form>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import SettingsCard from './SettingsCard.vue'
import LocationMapPicker from './LocationMapPicker.vue'
import SettingsSaveBar from './SettingsSaveBar.vue'
import RegionPackCard from './RegionPackCard.vue'
import SettingsNumberField from './SettingsNumberField.vue'
import SettingsSelectField from './SettingsSelectField.vue'

const props = defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()

// A click on the map fills both fields, and clears whatever the server said about the
// coordinates it is replacing, the way typing in one of them does.
function place({ latitude, longitude }) {
  props.form.fields.location_lat = latitude
  props.form.fields.location_lon = longitude
  props.form.errors.location_lat = ''
  props.form.errors.location_lon = ''
}
</script>
