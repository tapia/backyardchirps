<template>
  <div class="container d-flex justify-content-center mt-5">
    <div class="card login-card">
      <div class="card-body p-4">
        <h5 class="card-title mb-4">
          <i class="bi bi-shield-lock me-2"></i>{{ t('login.title') }}
        </h5>
        <form @submit.prevent="onSubmit">
          <div class="mb-3">
            <label class="form-label small">{{ t('login.username') }}</label>
            <input
              v-model="username"
              type="text"
              class="form-control"
              autocomplete="username"
              autofocus
              :disabled="loading"
            />
          </div>
          <div class="mb-3">
            <label class="form-label small">{{ t('login.password') }}</label>
            <input
              v-model="password"
              type="password"
              class="form-control"
              autocomplete="current-password"
              :disabled="loading"
            />
          </div>
          <div v-if="errorMessage" class="alert alert-danger py-2 small mb-3">
            {{ errorMessage }}
          </div>
          <button type="submit" class="btn btn-primary w-100" :disabled="loading">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>
            {{ t('login.submit') }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const { login } = useAuth()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')

async function onSubmit() {
  errorMessage.value = ''
  loading.value = true
  try {
    const user = await login(username.value, password.value)
    if (user.is_staff) {
      router.push(route.query.next || '/')
    } else {
      errorMessage.value = t('login.notAdmin')
    }
  } catch {
    errorMessage.value = t('login.invalidCredentials')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-card {
  width: 100%;
  max-width: 360px;
  background-color: var(--admin-card-bg);
  border: 1px solid var(--admin-accent);
  color: #fff;
}
.form-label {
  color: rgba(255, 255, 255, 0.75);
}
.form-control {
  background-color: var(--admin-input-bg);
  border-color: var(--admin-card-border);
  color: #fff;
}
.form-control:focus {
  background-color: var(--admin-input-bg);
  border-color: var(--admin-accent);
  color: #fff;
  box-shadow: 0 0 0 0.2rem rgba(var(--admin-accent-rgb), 0.25);
}
.form-control:disabled {
  background-color: var(--admin-input-bg-disabled);
  color: rgba(255, 255, 255, 0.4);
}
</style>
