/**
 * Stryker Mutation Testing Configuration
 * ========================================
 * Measures the quality of existing tests by introducing code mutations
 * and checking if tests detect them (kill the mutants).
 *
 * Target: Zustand stores (Phase 6-10 core functionality)
 * Runner: Vitest (parallel, per-test coverage)
 *
 * Usage:
 *   npx stryker run                          # Full mutation test
 *   npx stryker run --mutate "src/stores/*.ts"  # All stores
 *   npx stryker run --mutate "src/stores/terminalStore.ts"  # Single store
 */

// @ts-check
/** @type {import('@stryker-mutator/api/core').StrykerOptions} */
const config = {
  // CR-14 F-10: pnpm 의 격리(심볼릭 링크) 레이아웃에서는 Stryker 의 **자동 플러그인 탐색**이
  // `@stryker-mutator/*` 를 자기 자신의 설치 디렉터리에서만 스캔한다 — 그 디렉터리에는 core 의
  // 의존(api·instrumenter·util)만 있고 devDependency 인 vitest-runner 는 없다. 그래서 러너를
  // **명시적으로** 선언한다. 이 한 줄이 없으면 `Cannot find TestRunner plugin "vitest"` 로 죽고,
  // 아래 `vitest: {...}` 옵션도 스키마에 기여되지 않아 "Unknown stryker config option" 경고가 난다.
  plugins: ['@stryker-mutator/vitest-runner'],
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
    // Disable related-test finding — rely on the include pattern in vitest.config.ts instead
    related: false,
  },

  mutate: [
    // Store files (Phase 6-10)
    'src/stores/terminalStore.ts',
    'src/stores/outputStore.ts',
    'src/stores/localHistoryStore.ts',
    'src/stores/agentMonitorStore.ts',
    'src/plugin/pluginRegistry.ts',
    // Component files (Phase 11-12)
    'src/components/Editor/SearchPanel.tsx',
    'src/components/Editor/Editor.tsx',
    'src/components/Editor/FileTree.tsx',
    'src/components/Chat/ChatMessage.tsx',
  ],

  // These are IGNORE patterns — files to exclude from mutation AND test discovery.
  // DO NOT add test file patterns here or Stryker won't find any tests!
  ignorePatterns: [
    'src/**/*.d.ts',
    'stryker-tmp/**',
  ],

  reporters: ['progress', 'clear-text', 'html'],

  coverageAnalysis: 'perTest',

  concurrency: 4,

  timeoutMS: 10000,
  timeoutFactor: 1.5,

  thresholds: {
    high: 80,
    low: 60,
    break: 55,
  },

  dryRun: null,
  warnOnSlow: true,
  tempDirName: 'stryker-tmp',
};

export default config;
