<template>
  <ul class="nav nav-tabs nav-fill settings-tabs mb-4">
    <li v-for="tab in SETTINGS_TABS" :key="tab.name" class="nav-item">
      <RouterLink
        class="nav-link"
        :class="{ active: tab.name === active }"
        :to="`/settings/${tab.name}`"
      >
        <i class="bi" :class="tab.icon"></i>
        <span class="tab-label">{{ t(`page.settings.tabs.${tab.name}`) }}</span>
      </RouterLink>
    </li>
  </ul>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { SETTINGS_TABS } from './settingsTabs.js'

defineProps({
  active: { type: String, required: true },
})

const { t } = useI18n()
</script>

<style scoped>
/* The shape of .nav-tabs comes from style.css, shared with the species profile. Only the
   icon-and-label arrangement is set here. */
.nav-tabs.settings-tabs .nav-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.65rem 0.5rem;
  border-bottom-width: 3px;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}
.nav-tabs.settings-tabs .nav-link.active {
  background: rgba(var(--lichen-rgb), 0.07);
  border-bottom-color: var(--lichen);
}
/* Four labels do not fit across a narrow phone. The icons carry the tab on their own
   there, and the selected one keeps its label. */
@media (max-width: 400px) {
  .nav-tabs.settings-tabs .nav-link:not(.active) .tab-label {
    display: none;
  }
}
</style>
