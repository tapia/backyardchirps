<template>
  <SiteNavbar v-if="!isSetup" />
  <RouterView />
  <SiteFooter v-if="!isSetup" />
</template>

<script setup>
import { provide, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import SiteNavbar from './components/navbar/SiteNavbar.vue'
import SiteFooter from './components/common/SiteFooter.vue'

const { locale } = useI18n()
const route = useRoute()

// The wizard takes the whole page. It has its own language picker as a first step, and
// every navbar link would bounce straight back to it while setup is unfinished.
const isSetup = computed(() => route.name === 'setup')

// Pages read the current language via inject('lang') to pass it to API calls.
provide('lang', locale)
</script>
