import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
      '/setup': 'http://localhost:8000',
      '/species-data': 'http://localhost:8000',
    },
  },
})
