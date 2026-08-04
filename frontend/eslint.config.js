import pluginVue from 'eslint-plugin-vue'

export default [
  ...pluginVue.configs['flat/recommended'],
  {
    rules: {
      'vue/multi-word-component-names': 'off',
      // Reactive stores (e.g. useSettingsForm instances) are passed as props
      // and mutated by design; only flag reassigning the prop itself.
      'vue/no-mutating-props': ['error', { shallowOnly: true }],
    },
  },
]
