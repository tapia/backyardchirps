<template>
  <div>
    <label class="form-label small">{{ label }}</label>
    <input
      v-model="form.fields[name]"
      :type="type"
      class="form-control"
      :class="{ 'is-invalid': form.errors[name] }"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :disabled="form.loading"
      @input="form.errors[name] = ''"
    />
    <div v-if="form.errors[name]" class="invalid-feedback">{{ form.errors[name] }}</div>
    <div v-if="hint" class="field-hint">{{ hint }}</div>
  </div>
</template>

<script setup>
defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
  name: { type: String, required: true }, // setting name, as the API knows it
  label: { type: String, required: true },
  // 'password' only hides the value on screen. It is not a secret from whoever is
  // logged in as admin, since they are the one who typed it.
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  autocomplete: { type: String, default: 'off' },
  hint: { type: String, default: '' },
})
</script>
