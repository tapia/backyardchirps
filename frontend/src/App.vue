<template>
  <SiteNavbar />
  <RouterView />
  <SiteFooter />
</template>

<script setup>
import { provide } from 'vue'
import { useI18n } from 'vue-i18n'
import SiteNavbar from './components/navbar/SiteNavbar.vue'
import SiteFooter from './components/common/SiteFooter.vue'

const { locale } = useI18n()

// Pages read the current language via inject('lang') to pass it to API calls.
provide('lang', locale)
</script>
