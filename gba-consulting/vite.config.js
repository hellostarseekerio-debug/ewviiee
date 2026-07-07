import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// viteSingleFile inlines all JS/CSS into dist/index.html — one deployable file
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    chunkSizeWarningLimit: 4000,
  },
})
