<template>
  <div>
    <label class="form-label small">{{ label }}</label>
    <input
      v-model="form.fields[name]"
      type="number"
      :min="min"
      :max="max"
      :step="step"
      class="form-control"
      :class="{ 'is-invalid': form.errors[name], 'form-control-narrow': narrow }"
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
  min: { type: [String, Number], default: undefined },
  max: { type: [String, Number], default: undefined },
  step: { type: [String, Number], default: undefined },
  narrow: { type: Boolean, default: false },
  hint: { type: String, default: '' },
})
</script>
