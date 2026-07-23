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
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          // Core vendor — React, Router, Zustand (excludes @tanstack for separate chunk)
          if (id.includes('node_modules/react/') ||
              id.includes('node_modules/react-dom/') ||
              id.includes('node_modules/react-router') ||
              id.includes('node_modules/@remix-run/') ||
              id.includes('node_modules/zustand/')) {
            return 'vendor';
          }
          // @tanstack/react-query — data fetching (not needed on initial page load)
          if (id.includes('node_modules/@tanstack/')) {
            return 'query';
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
          // dompurify — HTML sanitizer, used by formatContent.ts independently
          if (id.includes('node_modules/dompurify') ||
              id.includes('node_modules/@types/dompurify')) {
            return 'dompurify';
          }
          // react-markdown + core markdown pipeline (without highlight.js)
          // Split from highlighting so non-code markdown loads faster.
          if (id.includes('node_modules/react-markdown') ||
              id.includes('node_modules/rehype-raw') ||
              id.includes('node_modules/rehype-stringify') ||
              id.includes('node_modules/remark-') ||
              id.includes('node_modules/mdast-') ||
              id.includes('node_modules/micromark') ||
              id.includes('node_modules/hast-util-') ||
              id.includes('node_modules/unist-') ||
              id.includes('node_modules/trim-lines') ||
              id.includes('node_modules/decode-named-character-reference') ||
              id.includes('node_modules/character-entities') ||
              id.includes('node_modules/property-information') ||
              id.includes('node_modules/comma-separated-tokens') ||
              id.includes('node_modules/space-separated-tokens') ||
              id.includes('node_modules/html-void-elements') ||
              id.includes('node_modules/@types/hast')) {
            return 'markdown-core';
          }
          // Syntax highlighting — heavy (~300KB), only needed for code blocks
          if (id.includes('node_modules/rehype-highlight') ||
              id.includes('node_modules/lowlight') ||
              id.includes('node_modules/@types/highlight') ||
              id.includes('node_modules/highlight.js') ||
              id.includes('node_modules/hast-util-to-text')) {
            return 'markdown-highlight';
          }
          // Utility packages: diff, types (used across multiple pages)
          if (id.includes('node_modules/diff') ||
              id.includes('node_modules/@types/diff')) {
            return 'utils';
          }
          // Small packages (< 10kB gzipped) stay bundled
        },
      },
    },
  },
});
