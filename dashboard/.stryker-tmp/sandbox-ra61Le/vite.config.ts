// @ts-nocheck
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const backendTarget = process.env.VITE_BACKEND_URL
  || process.env.AGK_BACKEND_URL
  || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    allowedHosts: ['antigravity-k.cloud'],
    proxy: {
      '/v1': { target: backendTarget, changeOrigin: true },
      '/api': { target: backendTarget, changeOrigin: true },
      '/ws': { target: backendTarget, changeOrigin: true, ws: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          // Core vendor — React, Router, Zustand
          if (id.includes('node_modules/react/') ||
              id.includes('node_modules/react-dom/') ||
              id.includes('node_modules/react-router') ||
              id.includes('node_modules/@remix-run/') ||
              id.includes('node_modules/zustand/') ||
              id.includes('node_modules/@tanstack/')) {
            return 'vendor';
          }
          // Monaco Editor — very large (800KB+), loaded only on editor pages
          if (id.includes('node_modules/monaco-editor') ||
              id.includes('node_modules/@monaco-editor')) {
            return 'monaco';
          }
          // xterm.js — terminal
          if (id.includes('node_modules/xterm')) {
            return 'terminal';
          }
          // Split.js — IDE layout
          if (id.includes('node_modules/split.js')) {
            return 'splitjs';
          }
          // DOMPurify — XSS sanitization (inlined due to small size)
          // (no separate chunk — it's tiny and gets bundled into the app shell)
        },
      },
    },
  },
});
