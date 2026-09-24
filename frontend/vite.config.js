import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api calls go to the Flask backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': process.env.VITE_API_URL || 'http://localhost:5000' },
  },
})
