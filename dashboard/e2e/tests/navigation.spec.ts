/**
 * Navigation E2E Test
 * ===================
 * Verifies sidebar navigation links work correctly.
 *
 * Based on "Phase 1: 코어 레이어 및 내비게이션" from test_process.md.
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

test.describe('Dashboard Navigation', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.handlePinModal();
  });

  test('should have visible sidebar navigation', async () => {
    await expect(dashboard.sidebar.first()).toBeVisible({ timeout: 5000 });
  });

  test('should navigate to chat page', async () => {
    await dashboard.goToChat();
    const chatInputVisible = await dashboard.chatInput.isVisible().catch(() => false);
    // Chat input may be visible or there may be a chat history panel
    const chatAreaVisible = await dashboard.page.locator('[class*="chat"], [class*="message"]').first().isVisible().catch(() => false);
    expect(chatInputVisible || chatAreaVisible).toBeTruthy();
  });
});
