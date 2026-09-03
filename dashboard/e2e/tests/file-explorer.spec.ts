/**
 * File Explorer E2E Test (Agent Workspace composition)
 * ====================================================
 * The legacy IDE explorer panel was replaced by the right-hand 환경 rail
 * (EnvironmentPanel). File browsing now lives in:
 *   - 환경 tab  → 파일 액티브티 (git status based file list)
 *   - 코드 tab  → the code editor (Editor.tsx, `.ide-editor`)
 *   - 변경 tab  → the change review panel (ChangePanel)
 *
 * Scenario:
 *   1. Navigate to chat page
 *   2. Verify the environment rail renders with the file activity list
 *   3. Open the 코드 tab and verify the editor mounts
 *   4. Open the 변경 tab and verify the change panel mounts
 *   5. Toggle the rail closed and re-open
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

test.describe('Environment Rail — file browsing', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.goToChat();
  });

  test('should render the environment rail by default', async () => {
    const rail = dashboard.page.locator('.agk-env-panel');
    await expect(rail).toBeVisible({ timeout: 5000 });

    const envTab = rail.locator('.env-tab').filter({ hasText: '환경' });
    await expect(envTab).toHaveClass(/active/);
  });

  test('should show file activity from git status', async () => {
    const rail = dashboard.page.locator('.agk-env-panel');
    await expect(rail).toBeVisible({ timeout: 5000 });

    // Either git files render, or the empty state when the tree is clean
    const fileRows = rail.locator('.env-file-row');
    const empty = rail.locator('.env-sub-empty');
    await expect(fileRows.or(empty).first()).toBeVisible({ timeout: 8000 });
  });

  test('should mount the editor from the 코드 tab', async () => {
    const rail = dashboard.page.locator('.agk-env-panel');
    await rail.locator('.env-tab').filter({ hasText: '코드' }).click();

    const editor = dashboard.page.locator('.ide-editor');
    await expect(editor).toBeVisible({ timeout: 8000 });
  });

  test('should mount the change panel from the 변경 tab', async () => {
    const rail = dashboard.page.locator('.agk-env-panel');
    await rail.locator('.env-tab').filter({ hasText: '변경' }).click();

    const changePanel = dashboard.page.locator('.change-panel');
    await expect(changePanel).toBeVisible({ timeout: 8000 });
  });

  test('should toggle the environment rail closed and open', async () => {
    const toggle = dashboard.page.locator('[aria-label="환경 패널 토글"]');
    await expect(toggle).toBeVisible({ timeout: 5000 });

    await toggle.click();
    await expect(dashboard.page.locator('.agk-env-panel')).toHaveCount(0);

    await toggle.click();
    await expect(dashboard.page.locator('.agk-env-panel')).toBeVisible();
  });
});
