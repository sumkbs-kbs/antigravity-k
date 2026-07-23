/**
 * Playwright E2E Configuration
 * =============================
 * Browser-based end-to-end tests for Antigravity-K Dashboard.
 *
 * Prerequisites:
 *   - Backend server running on AGK_BACKEND_URL (default: http://127.0.0.1:8012)
 *   - Npx playwright browsers installed via: npx playwright install chromium
 *
 * Usage:
 *   npm run e2e              # Run all E2E tests (requires backend + dashboard)
 *   npm run e2e:headed       # Run in headed mode (watch the browser)
 *   npm run e2e:ui           # Run with Playwright UI mode
 *   npm run e2e:report       # View last test report
 */

import { defineConfig } from '@playwright/test';

const BACKEND_URL = process.env.AGK_BACKEND_URL
  || process.env.VITE_BACKEND_URL
  || 'http://127.0.0.1:8012';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['html', { outputFolder: 'e2e-report' }],
    ['list'],
  ],
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },

  use: {
    baseURL: BACKEND_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: !process.env.E2E_HEADED,
    viewport: { width: 1280, height: 800 },
    ignoreHTTPSErrors: true,
  },

  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        launchOptions: {
          args: ['--no-sandbox', '--disable-setuid-sandbox'],
        },
      },
    },
  ],
});
