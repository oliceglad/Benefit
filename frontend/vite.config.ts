import path from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const directory = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(directory, './src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.BENEFIT_GATEWAY_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/.well-known': {
        target: process.env.BENEFIT_GATEWAY_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
