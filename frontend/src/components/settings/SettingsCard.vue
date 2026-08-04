<template>
  <div class="settings-card">
    <h6 class="settings-section-title"><i class="bi me-2" :class="icon"></i>{{ title }}</h6>
    <form @submit.prevent="form.save()">
      <slot />
      <button type="submit" class="btn btn-primary btn-sm" :disabled="form.loading || form.saved">
        <i v-if="form.saved" class="bi bi-check-lg me-1"></i>
        {{ form.saved ? t('page.settings.saved') : t('page.settings.save') }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  form: { type: Object, required: true }, // a useSettingsForm() instance
})

const { t } = useI18n()
</script>

<!-- Unscoped on purpose: these rules must reach the field components rendered
     in the slot, so they are namespaced under .settings-card instead. -->
<style>
.settings-card {
  background-color: var(--admin-card-bg);
  border: 1px solid var(--admin-card-border);
  border-radius: 8px;
  padding: 1.25rem;
}
.settings-card .settings-section-title {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 1rem;
}
.settings-card .form-label {
  color: rgba(255, 255, 255, 0.65);
}
.settings-card .form-control,
.settings-card .form-select {
  background-color: var(--admin-input-bg);
  border-color: var(--admin-card-border);
  color: #fff;
}
.settings-card .form-control:focus,
.settings-card .form-select:focus {
  background-color: var(--admin-input-bg);
  border-color: var(--admin-accent);
  color: #fff;
  box-shadow: 0 0 0 0.2rem rgba(var(--admin-accent-rgb), 0.25);
}
.settings-card .form-control:disabled,
.settings-card .form-select:disabled {
  background-color: var(--admin-input-bg-disabled);
  color: rgba(255, 255, 255, 0.4);
}
.settings-card .form-control.is-invalid,
.settings-card .form-select.is-invalid {
  border-color: var(--admin-danger);
}
.settings-card .invalid-feedback {
  color: var(--admin-danger-text);
}
.settings-card .form-check-label {
  color: rgba(255, 255, 255, 0.65);
}
.settings-card .form-check-input:checked {
  background-color: var(--admin-accent);
  border-color: var(--admin-accent);
}
.settings-card .form-control-narrow {
  max-width: 120px;
}
.settings-card .field-hint {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 0.3rem;
  margin-bottom: 0;
}
</style>
