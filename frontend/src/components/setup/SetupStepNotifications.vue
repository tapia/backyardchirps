<template>
  <div>
    <p class="step-intro">{{ t('setup.notifications.intro') }}</p>

    <SettingsTextField
      class="mb-3"
      :form="form"
      name="telegram_token"
      type="password"
      :label="t('page.settings.telegramToken')"
      :hint="t('page.settings.telegramTokenHint')"
    />
    <SettingsTextField
      class="mb-3"
      :form="form"
      name="telegram_chat_id"
      :label="t('page.settings.telegramChatId')"
    />
    <SettingsSelectField
      class="mb-4"
      :form="form"
      name="notifications_language"
      :label="t('page.settings.notificationsLanguage')"
      :options="[
        { value: 'en', label: t('page.settings.notificationsLanguageEn') },
        { value: 'es', label: t('page.settings.notificationsLanguageEs') },
      ]"
    />

    <p class="field-hint mb-3">{{ t('setup.notifications.rulesLater') }}</p>

    <SettingsTextField
      class="mb-3"
      :form="form"
      name="xeno_canto_api_key"
      type="password"
      :label="t('page.settings.xenoCantoApiKey')"
      :hint="t('page.settings.xenoCantoApiKeyHint')"
    />
    <SettingsTextField
      :form="form"
      name="ipgeolocation_api_key"
      type="password"
      :label="t('page.settings.ipgeolocationApiKey')"
      :hint="t('page.settings.ipgeolocationApiKeyHint')"
    />
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import SettingsTextField from '../settings/SettingsTextField.vue'
import SettingsSelectField from '../settings/SettingsSelectField.vue'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()
</script>
