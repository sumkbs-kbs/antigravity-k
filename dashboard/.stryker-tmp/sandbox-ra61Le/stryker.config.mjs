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
// @ts-nocheck


// 
/** @type {import('@stryker-mutator/api/core').StrykerOptions} */
const config = {
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
    // Disable related-test finding — rely on the include pattern in vitest.config.ts instead
    related: false,
  },

  mutate: [
    'src/stores/terminalStore.ts',
    'src/stores/outputStore.ts',
    'src/stores/localHistoryStore.ts',
    'src/stores/agentMonitorStore.ts',
    'src/plugin/pluginRegistry.ts',
  ],

  ignorePatterns: [
    'src/**/__tests__/**',
    'src/**/*.test.ts',
    'src/**/*.test.tsx',
    'src/**/*.spec.ts',
    'src/**/*.d.ts',
    '.stryker-tmp/**',
    'reports/**',
  ],

  reporters: ['progress', 'clear-text'],

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
  tempDir: '.stryker-tmp',
};

export default config;
