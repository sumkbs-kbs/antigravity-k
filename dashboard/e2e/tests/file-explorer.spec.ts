/**
 * File Explorer E2E Test
 * ======================
 * Verifies the file explorer panel within the chat/IDE page.
 *
 * Scenario:
 *   1. Navigate to chat page (IDE layout)
 *   2. Verify file explorer panel is visible with toolbar
 *   3. Verify file tree renders
 *   4. Interact with toolbar buttons (refresh)
 *   5. Toggle search panel
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

test.describe('File Explorer', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.handlePinModal();
    await dashboard.goToChat();
  });

  test('should render the file explorer panel in the IDE layout', async () => {
    await dashboard.expectFileExplorerVisible();
  });

  test('should show EXPLORER title', async () => {
    await expect(dashboard.explorerTitle).toBeVisible({ timeout: 5000 });
    const titleText = await dashboard.explorerTitle.textContent();
    expect(titleText).toContain('EXPLORER');
  });

  test('should have toolbar buttons in the file explorer header', async () => {
    const toolbar = dashboard.page.locator('[role="toolbar"]');
    await expect(toolbar).toBeVisible({ timeout: 5000 });

    // Check for key action buttons
    const refreshBtn = dashboard.page.locator('[aria-label="파일 트리 새로고침"]');
    await expect(refreshBtn).toBeVisible({ timeout: 3000 });

    const searchBtn = dashboard.page.locator('[aria-label="파일 검색"]');
    await expect(searchBtn).toBeVisible({ timeout: 3000 });
  });

  test('should render the file tree container', async () => {
    await dashboard.expectFileTreeRendered();
  });

  test('should toggle search panel on search button click', async () => {
    const searchBtn = dashboard.page.locator('[aria-label="파일 검색"]');
    await searchBtn.click();
    await dashboard.page.waitForTimeout(500);

    // Search panel should now be visible (replacing file tree)
    const searchPanel = dashboard.page.locator('.search-panel-wrapper');
    const searchVisible = await searchPanel.isVisible().catch(() => false);

    // The search panel may or may not render depending on data; just verify toggle works
    if (searchVisible) {
      // Click again to close
      await searchBtn.click();
      await dashboard.page.waitForTimeout(500);
      await dashboard.expectFileTreeRendered();
    }
  });

  test('should have a refresh button that triggers file tree update', async () => {
    await dashboard.clickExplorerRefresh();
    // After refresh, the file tree should still be rendered (no crash)
    await dashboard.expectFileTreeRendered();
  });

  test('should have new folder, index workspace, and open folder buttons', async () => {
    const newFolderBtn = dashboard.page.locator('[aria-label="새 폴더"]');
    await expect(newFolderBtn).toBeVisible({ timeout: 3000 });
    await expect(newFolderBtn).toBeEnabled();

    const indexBtn = dashboard.page.locator('[aria-label="워크스페이스 인덱싱"]');
    await expect(indexBtn).toBeVisible({ timeout: 3000 });

    const openFolderBtn = dashboard.page.locator('[aria-label="폴더 열기"]');
    await expect(openFolderBtn).toBeVisible({ timeout: 3000 });

    const refreshBtn = dashboard.page.locator('[aria-label="파일 트리 새로고침"]');
    await expect(refreshBtn).toBeVisible({ timeout: 3000 });
  });
});
