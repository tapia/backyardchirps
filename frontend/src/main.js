import { createApp, watch } from 'vue'
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.css'
import './style.css'
import App from './App.vue'
import router from './router/index.js'
import i18n, { LOCALE_STORAGE_KEY } from './i18n.js'
import { bsTooltip } from './directives/bsTooltip.js'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import localizedFormat from 'dayjs/plugin/localizedFormat'
import 'dayjs/locale/es'

dayjs.extend(relativeTime)
dayjs.extend(localizedFormat)
dayjs.locale(i18n.global.locale.value)
watch(i18n.global.locale, (lang) => {
  dayjs.locale(lang)
  localStorage.setItem(LOCALE_STORAGE_KEY, lang)
})

createApp(App).use(router).use(i18n).directive('bs-tooltip', bsTooltip).mount('#app')
