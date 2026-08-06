<template>
  <form @submit.prevent="submit">
    <p class="step-intro">{{ t('setup.admin.intro') }}</p>

    <div v-if="tokenRequired" class="mb-3">
      <label class="form-label small">{{ t('setup.admin.token') }}</label>
      <input
        v-model="token"
        type="text"
        class="form-control"
        autocomplete="off"
        spellcheck="false"
        :disabled="loading"
      />
      <div class="field-hint">{{ t('setup.admin.tokenHint') }}</div>
    </div>

    <div class="mb-3">
      <label class="form-label small">{{ t('setup.admin.username') }}</label>
      <input
        v-model="username"
        type="text"
        class="form-control"
        autocomplete="username"
        :disabled="loading"
      />
    </div>

    <div class="mb-3">
      <label class="form-label small">{{ t('setup.admin.password') }}</label>
      <input
        v-model="password"
        type="password"
        class="form-control"
        autocomplete="new-password"
        :disabled="loading"
      />
    </div>

    <div v-if="errorMessage" class="alert alert-danger py-2 small mb-3">
      {{ errorMessage }}
      <ul v-if="errorDetails.length" class="mb-0 mt-2 ps-3">
        <li v-for="detail in errorDetails" :key="detail">{{ detail }}</li>
      </ul>
    </div>

    <button type="submit" class="btn btn-primary w-100" :disabled="loading">
      <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>
      {{ t('setup.admin.submit') }}
    </button>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { claimSetup, createSetupAdmin } from '../../api/index.js'
import { useAuth } from '../../composables/useAuth.js'

defineProps({
  tokenRequired: { type: Boolean, required: true },
})

const emit = defineEmits(['done'])

const { t } = useI18n()
const { refresh: refreshSession } = useAuth()

const token = ref('')
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const errorDetails = ref([])

async function submit() {
  errorMessage.value = ''
  errorDetails.value = []
  loading.value = true
  try {
    // Two calls, one button: the token buys the right to create the account, and on
    // its own it is not worth a step of its own.
    await claimSetup(token.value)
    await createSetupAdmin(username.value, password.value)
    // The wizard is now logged in as the admin it just made. Tell the rest of the app,
    // so the navbar and the admin guard agree once the wizard is over.
    await refreshSession()
    emit('done')
  } catch (error) {
    const data = error.response?.data ?? {}
    errorMessage.value = data.error
      ? t(`setup.errors.${data.error}`)
      : t('setup.errors.unreachable')
    errorDetails.value = data.messages ?? []
  } finally {
    loading.value = false
  }
}
</script>
