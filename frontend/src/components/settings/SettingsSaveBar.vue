<template>
  <div class="settings-save-bar">
    <button
      type="submit"
      class="btn btn-primary btn-sm"
      :disabled="form.loading || form.saved || !form.dirty"
    >
      <i v-if="form.saved" class="bi bi-check-lg me-1"></i>
      {{ form.saved ? t('page.settings.saved') : t('page.settings.save') }}
    </button>
    <span v-if="form.dirty && !form.loading" class="save-note">
      {{ t('page.settings.unsaved') }}
    </span>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()
</script>

<style scoped>
/* Sticky, because the notifications tab is longer than a screen and the one button that
   saves it should never be the thing you have to go looking for. */
.settings-save-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 0;
  background-color: var(--paper);
  border-top: 1px solid var(--limestone);
}
.save-note {
  font-size: 0.8125rem;
  color: var(--slate);
}
</style>
