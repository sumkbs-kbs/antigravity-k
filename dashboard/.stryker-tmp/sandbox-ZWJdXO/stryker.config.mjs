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
  // ─── Test Runner ───────────────────────────────────────────
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
  },

  // ─── Mutation Scope ────────────────────────────────────────
  // Mutate only Zustand store files (not React components, not tests)
  mutate: [
    'src/stores/terminalStore.ts',
    'src/stores/outputStore.ts',
    'src/stores/localHistoryStore.ts',
    'src/stores/agentMonitorStore.ts',
    'src/plugin/pluginRegistry.ts',
    'src/plugin/pluginTypes.ts',
  ],
  // Do NOT mutate these
  ignorePatterns: [
    'src/**/__tests__/**',
    'src/**/*.test.ts',
    'src/**/*.test.tsx',
    'src/**/*.spec.ts',
    'src/**/*.d.ts',
  ],

  // ─── Reporters ─────────────────────────────────────────────
  reporters: ['progress', 'clear-text', 'html'],

  // ─── Coverage ──────────────────────────────────────────────
  // Per-test coverage analysis for faster mutation testing
  coverageAnalysis: 'perTest',

  // ─── Concurrency ──────────────────────────────────────────
  // Use all available CPU cores (for CI/CD, set to 2-4)
  concurrency: 4,

  // ─── Timeouts ──────────────────────────────────────────────
  timeoutMS: 10000,
  timeoutFactor: 1.5,

  // ─── Thresholds ────────────────────────────────────────────
  // Fail CI if mutation score drops below these thresholds
  thresholds: {
    high: 80,
    low: 60,
    break: 50,
  },

  // ─── Misc ──────────────────────────────────────────────────
  // Enable dry run to validate test setup before mutating
  // (set to null to disable; integer to limit mutants)
  dryRun: null,

  // Warn about slow mutants (more than 2x average)
  warnOnSlow: true,

  // Temp directory for mutant test runs
  tempDir: '.stryker-tmp',
};

export default config;
