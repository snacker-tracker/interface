import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend build (`snacker build --out ../public-data`) writes the static JSON
// the app reads. Serving that folder as Vite's public dir makes it available at
// /data/... in dev and copies it into dist/ on `vite build`.
export default defineConfig({
  plugins: [react()],
  publicDir: '../public-data',
})
