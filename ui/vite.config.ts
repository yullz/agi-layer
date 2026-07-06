import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' so the static build is servable from any local path (file:// or a
// localhost static server) with no host assumptions.
export default defineConfig({
  plugins: [react()],
  base: './',
})
