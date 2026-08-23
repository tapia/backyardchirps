<template>
  <div>
    <label class="form-label small">{{ label }}</label>
    <div class="input-group input-group-narrow">
      <input
        v-model="percent"
        type="number"
        min="0"
        max="100"
        step="1"
        inputmode="numeric"
        class="form-control"
        :class="{ 'is-invalid': form.errors[name] }"
        :disabled="form.loading"
        @input="form.errors[name] = ''"
      />
      <span class="input-group-text">%</span>
    </div>
    <!-- Outside the group, which is only as wide as the number, so the message has the
         whole field to wrap in. d-block because Bootstrap only reveals the feedback next
         to the invalid input itself. -->
    <div v-if="form.errors[name]" class="invalid-feedback d-block">{{ form.errors[name] }}</div>
    <div v-if="hint" class="field-hint">{{ hint }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// A confidence setting. The API stores it as a number from 0 to 1, which is what BirdNET
// scores a detection with, but every other place the site shows a confidence writes it as
// a whole percentage, so that is what this field edits.
const props = defineProps({
  form: { type: Object, required: true }, // a useSettingsForm() instance
  name: { type: String, required: true }, // setting name, as the API knows it
  label: { type: String, required: true },
  hint: { type: String, default: '' },
})

const percent = computed({
  get() {
    const stored = Number.parseFloat(props.form.fields[props.name])
    return Number.isNaN(stored) ? '' : Math.round(stored * 100)
  },
  set(value) {
    // An empty field is left empty rather than sent as a zero, so the server answers with
    // the same "this is not a confidence" it gives any other unusable value.
    props.form.fields[props.name] = value === '' || value === null ? '' : value / 100
  },
})
</script>
