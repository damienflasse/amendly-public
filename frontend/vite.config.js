import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },

  // -------------------------------------------------------------------------
  // Dev server — proxies /api to the FastAPI backend
  // -------------------------------------------------------------------------
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },

  // -------------------------------------------------------------------------
  // Production build optimisations
  // -------------------------------------------------------------------------
  build: {
    // Target modern browsers — smaller/faster output (no IE11 polyfills)
    target: 'es2020',

    // Inline small assets as base64 — reduces HTTP requests
    // Images and fonts ≤ 8 kB are inlined (default: 4 kB)
    assetsInlineLimit: 8192,

    rollupOptions: {
      output: {
        // Manual chunking — splits vendor code from app code.
        // Vendor chunks (React, Router) change less often than app code,
        // so browsers can cache them across deploys.
        manualChunks(id) {
          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/')
          ) {
            return 'vendor-react'
          }
          if (
            id.includes('node_modules/react-router-dom/') ||
            id.includes('node_modules/react-router/')
          ) {
            return 'vendor-router'
          }
          if (id.includes('node_modules/zustand/')) {
            return 'vendor-zustand'
          }
        },
      },
    },
  },

  // -------------------------------------------------------------------------
  // SSR build config — used by `vite build --ssr src/entry-server.jsx`
  // to produce the Node.js bundle consumed by scripts/prerender.js
  // -------------------------------------------------------------------------
  ssr: {
    noExternal: [],
  },
})
