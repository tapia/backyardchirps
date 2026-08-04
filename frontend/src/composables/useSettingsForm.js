import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { saveSettings } from '../api/index.js'

// State and save flow for one card on the settings page. `initialFields`
// maps setting names (as the API knows them) to default values; each card
// saves only its own fields and shows per-field validation errors.
export function useSettingsForm(initialFields) {
  const { t } = useI18n()

  const form = reactive({
    fields: { ...initialFields },
    errors: Object.fromEntries(Object.keys(initialFields).map((name) => [name, ''])),
    loading: false,
    saved: false,
    load,
    save,
  })

  function load(settings) {
    for (const name of Object.keys(form.fields)) {
      form.fields[name] = settings[name] ?? initialFields[name]
    }
  }

  async function save() {
    form.loading = true
    form.saved = false
    for (const name of Object.keys(form.errors)) form.errors[name] = ''
    try {
      await saveSettings({ ...form.fields })
      form.saved = true
      setTimeout(() => {
        form.saved = false
      }, 2000)
    } catch (error) {
      const responseErrors = error.response?.data?.errors ?? {}
      for (const name of Object.keys(form.errors)) {
        const errorCode = responseErrors[name]
        form.errors[name] = errorCode ? t(`page.settings.errors.${errorCode}`) : ''
      }
    } finally {
      form.loading = false
    }
  }

  return form
}
