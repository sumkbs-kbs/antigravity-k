import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

function keepDisabledRulesAndWarnOnTheRest(rules) {
  return Object.fromEntries(
    Object.entries(rules).map(([name, setting]) => {
      const severity = Array.isArray(setting) ? setting[0] : setting;
      if (severity === 0 || severity === 'off') {
        return [name, setting];
      }
      return [name, Array.isArray(setting) ? ['warn', ...setting.slice(1)] : 'warn'];
    }),
  );
}

const baselineRules = Object.assign(
  {},
  js.configs.recommended.rules,
  ...tseslint.configs.recommended.map((config) => config.rules ?? {}),
  reactHooks.configs.flat.recommended.rules,
);

export default tseslint.config(
  {
    ignores: [
      '.stryker-tmp/**',
      'coverage/**',
      'dist/**',
      'e2e-report/**',
      'node_modules/**',
      'playwright-report/**',
      'stryker-tmp/**',
      'test-results/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ...reactHooks.configs.flat.recommended,
    files: ['src/**/*.{ts,tsx}'],
  },
  {
    files: ['**/*.{js,mjs,cjs,ts,tsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: 'warn',
    },
    plugins: {
      'react-hooks': reactHooks,
    },
    // Existing rule debt remains visible while syntax and configuration failures stay fatal.
    rules: keepDisabledRulesAndWarnOnTheRest(baselineRules),
  },
);
