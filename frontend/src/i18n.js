import { createI18n } from 'vue-i18n'
import en from './locales/en.js'
import es from './locales/es.js'
import { LANGUAGE_OPTIONS } from './locales/languageOptions.js'

export const LOCALE_STORAGE_KEY = 'locale'
const DEFAULT_LOCALE = 'es'

function initialLocale() {
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY)
  const isSupported = LANGUAGE_OPTIONS.some((option) => option.value === stored)
  return isSupported ? stored : DEFAULT_LOCALE
}

export default createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: { en, es },
})
