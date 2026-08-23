<template>
  <form class="settings-form" @submit.prevent="form.save()">
    <SettingsCard icon="bi-send" :title="t('page.settings.telegram')">
      <SettingsTextField
        class="mb-3"
        :form="form"
        name="telegram_token"
        type="password"
        :label="t('page.settings.telegramToken')"
        :hint="t('page.settings.telegramTokenHint')"
      />
      <SettingsTextField
        :form="form"
        name="telegram_chat_id"
        :label="t('page.settings.telegramChatId')"
      />
    </SettingsCard>

    <SettingsCard icon="bi-bell" :title="t('page.settings.notificationRules')">
      <SettingsSelectField
        class="mb-3"
        :form="form"
        name="notifications_language"
        :label="t('page.settings.notificationsLanguage')"
        :options="[
          { value: 'en', label: t('page.settings.notificationsLanguageEn') },
          { value: 'es', label: t('page.settings.notificationsLanguageEs') },
        ]"
      />
      <NotificationRuleField
        class="mb-3"
        :form="form"
        switch-id="notifPendingValidation"
        :label="t('page.settings.notificationsPendingValidation')"
        enabled-field="notifications_pending_validation_enabled"
      />
      <NotificationRuleField
        class="mb-3"
        :form="form"
        switch-id="notifNewSpecies"
        :label="t('page.settings.notificationsNewSpecies')"
        enabled-field="notifications_new_species_enabled"
        confidence-field="notifications_new_species_confidence"
      />
      <NotificationRuleField
        class="mb-3"
        :form="form"
        switch-id="notifFirstYear"
        :label="t('page.settings.notificationsFirstYear')"
        enabled-field="notifications_first_year_enabled"
        confidence-field="notifications_first_year_confidence"
      />
      <NotificationRuleField
        class="mb-3"
        :form="form"
        switch-id="notifFirstToday"
        :label="t('page.settings.notificationsFirstToday')"
        enabled-field="notifications_first_today_enabled"
        confidence-field="notifications_first_today_confidence"
      />
      <NotificationRuleField
        class="mb-3"
        :form="form"
        switch-id="notifLongAbsent"
        :label="t('page.settings.notificationsLongAbsent')"
        enabled-field="notifications_long_absent_enabled"
        confidence-field="notifications_long_absent_confidence"
        days-field="notifications_long_absent_days"
      />
      <NotificationRuleField
        :form="form"
        switch-id="notifRare"
        :label="t('page.settings.notificationsRare')"
        enabled-field="notifications_rare_enabled"
        confidence-field="notifications_rare_confidence"
      />
    </SettingsCard>

    <SettingsSaveBar :form="form" />
  </form>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import SettingsCard from './SettingsCard.vue'
import SettingsSaveBar from './SettingsSaveBar.vue'
import SettingsSelectField from './SettingsSelectField.vue'
import SettingsTextField from './SettingsTextField.vue'
import NotificationRuleField from './NotificationRuleField.vue'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()
</script>
