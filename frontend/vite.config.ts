import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on 127.0.0.1:8000 (make api); /api is proxied so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false, ws: false } } },
  preview: { proxy: { '/api': { target: 'http://127.0.0.1:8000' } } },
  build: { chunkSizeWarningLimit: 900 },
})
