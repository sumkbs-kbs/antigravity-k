/**
 * Health & Dashboard Load E2E Test
 * =================================
 * Verifies the dashboard loads correctly, title is present, and core DOM renders.
 *
 * Based on "Phase 1: 코어 레이어 및 내비게이션" from test_process.md.
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

test.describe('Dashboard Health & Load', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
  });

  test('should load the dashboard with correct title', async () => {
    await dashboard.expectTitle();
  });

  test('should render the app root element', async () => {
    await dashboard.expectAppRoot();
  });

  test('should respond to health endpoint', async ({ page }) => {
    const response = await page.request.get('/health');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('status');
    expect(body.status).toBe('ok');
  });

  test('should respond to v1 health endpoint', async ({ page }) => {
    const response = await page.request.get('/v1/health');
    expect(response.status()).toBe(200);
  });
});
