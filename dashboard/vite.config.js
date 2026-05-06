import { defineConfig } from 'vite';

const backendTarget = process.env.VITE_BACKEND_URL
  || process.env.AGK_BACKEND_URL
  || 'http://127.0.0.1:8000';

export default defineConfig({
  root: '.',
  server: {
    port: 5173,
    host: '0.0.0.0', // 외부 기기(모바일 등)에서 접근 허용
    // Python FastAPI 백엔드로 API 프록시
    proxy: {
      '/v1': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: backendTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
