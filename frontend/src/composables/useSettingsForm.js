import { reactive, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { saveSettings } from '../api/index.js'

// State and save flow for one tab of the settings page. `initialFields`
// maps setting names (as the API knows them) to default values; each tab
// saves only its own fields and shows per-field validation errors.
export function useSettingsForm(initialFields) {
  const { t } = useI18n()

  const fields = reactive({ ...initialFields })

  // What the fields held the last time they came from the server. The save button reads
  // it through `dirty`, so a tab nobody has touched cannot be saved.
  const savedFields = ref({ ...initialFields })

  const form = reactive({
    fields,
    errors: Object.fromEntries(Object.keys(initialFields).map((name) => [name, ''])),
    loading: false,
    saved: false,
    dirty: computed(() => JSON.stringify(fields) !== JSON.stringify(savedFields.value)),
    load,
    save,
  })

  function load(settings) {
    for (const name of Object.keys(fields)) {
      fields[name] = settings[name] ?? initialFields[name]
    }
    savedFields.value = { ...fields }
  }

  async function save() {
    form.loading = true
    form.saved = false
    for (const name of Object.keys(form.errors)) form.errors[name] = ''
    try {
      await saveSettings({ ...fields })
      savedFields.value = { ...fields }
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
