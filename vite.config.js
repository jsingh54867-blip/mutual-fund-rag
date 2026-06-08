import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist',
  },
  server: {
    port: 3000,
    proxy: {
      '/chat': 'http://localhost:5000',
      '/health': 'http://localhost:5000',
      '/sources': 'http://localhost:5000',
    },
  },
})
