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
    break: 50,
  },

  dryRun: null,
  warnOnSlow: true,
  tempDirName: 'stryker-tmp',
};

export default config;
