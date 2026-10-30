/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { buildStampFrom } from './src/buildStamp.ts'

// The backend build (`snacker build --out ../public-data`) writes the static JSON
// the app reads. Serving that folder as Vite's public dir makes it available at
// /data/... in dev and copies it into dist/ on `vite build`.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  publicDir: '../public-data',
  define: {
    // Tests run in CI too, where Actions' variables are set; they get no stamp, like a local build.
    __BUILD_STAMP__: JSON.stringify(mode === 'test' ? null : buildStampFrom(process.env)),
  },
  test: {
    // lcov is what CI uploads to qlty.sh; paths in it are relative to frontend/.
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      reporter: ['text', 'lcov'],
      reportsDirectory: 'reports',
    },
  },
}))
