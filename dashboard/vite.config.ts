import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-only proxy so the SPA and the FastAPI server share an origin locally,
// matching the single-domain setup on Vercel.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
