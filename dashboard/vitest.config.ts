import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

import { createAliases } from './vite.alias';
import { buildStampDefine } from './buildStamp';

const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  // CR-10: 빌드와 동일한 provenance 상수를 테스트에도 주입한다.
  define: buildStampDefine,
  resolve: {
    // 빌드와 동일한 해석 규칙을 공유한다(CR-09: cytoscape 깊은 import, monaco 워커).
    alias: [
      // jsdom에는 monaco가 로드 시 요구하는 브라우저 API가 없고 ESM이 수 MB다.
      // 편집기 컴포넌트 테스트는 어차피 wrapper를 mock하므로 스텁으로 대체한다.
      // `?worker` 쿼리가 붙은 하위 specifier까지 한 번에 잡는다.
      { find: /^monaco-editor/, replacement: path.join(dashboardRoot, 'src/tests/monacoStub.ts') },
      // `?worker` import는 브라우저 전용이라 jsdom에서 해석할 수 없다.
      { find: /^(?:.*\/)?monacoWorkers(?:\.ts)?$/, replacement: path.join(dashboardRoot, 'src/tests/monacoWorkersStub.ts') },
      ...Object.entries(createAliases()).map(([find, replacement]) => ({ find, replacement })),
    ],
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.*', 'src/tests/**'],
    },
  },
  ssr: {
    noExternal: ['zod'],
  },
});
