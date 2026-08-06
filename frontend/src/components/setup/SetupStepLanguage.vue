<template>
  <div>
    <p class="step-intro">{{ t('setup.language.intro') }}</p>
    <div class="d-grid gap-2">
      <button
        v-for="option in LANGUAGE_OPTIONS"
        :key="option.value"
        type="button"
        class="btn btn-outline-light text-start language-option"
        :class="{ selected: locale === option.value }"
        @click="choose(option.value)"
      >
        <i class="bi bi-check-lg me-2 check"></i>{{ option.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { LANGUAGE_OPTIONS } from '../../locales/languageOptions.js'

const { t, locale } = useI18n()

function choose(value) {
  locale.value = value
}
</script>

<style scoped>
.language-option .check {
  visibility: hidden;
}
.language-option.selected {
  border-color: var(--admin-accent);
  background-color: rgba(var(--admin-accent-rgb), 0.15);
}
.language-option.selected .check {
  visibility: visible;
}
</style>
