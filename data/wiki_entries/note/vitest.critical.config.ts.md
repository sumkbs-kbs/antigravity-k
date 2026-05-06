---
id: 149
category: note
tags: []
created: 2026-05-04T09:42:52.472054
---

# vitest.critical.config.ts

```typescript
import { resolve } from 'path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./test/setup.ts'],
    include: ['test/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: [
        'src/main/ipc/guards.ts',
        'src/main/ipc/configValidation.ts',
        'src/main/utils/pathDecoder.ts',
        'src/main/services/discovery/ProjectPathResolver.ts',
      ],
      thresholds: {
        lines: 65,
        functions: 75,
        branches: 60,
        statements: 65,
      },
    },
  },
  resolve: {
    alias: {
      '@shared': resolve(__dirname, 'src/shared'),
      '@main': resolve(__dirname, 'src/main'),
      '@renderer': resolve(__dirname, 'src/renderer'),
    },
  },
});
```
