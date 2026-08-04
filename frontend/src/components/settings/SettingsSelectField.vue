<template>
  <div>
    <label class="form-label small">{{ label }}</label>
    <select
      v-model="form.fields[name]"
      class="form-select"
      :disabled="form.loading"
      @change="form.errors[name] = ''"
    >
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <div v-if="form.errors[name]" class="invalid-feedback d-block">{{ form.errors[name] }}</div>
    <div v-if="hint" class="field-hint">{{ hint }}</div>
  </div>
</template>

<script setup>
defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
  name: { type: String, required: true }, // setting name, as the API knows it
  label: { type: String, required: true },
  options: { type: Array, required: true }, // [{ value, label }]
  hint: { type: String, default: '' },
})
</script>
