/**
 * Git E2E Test
 * ============
 * Verifies the Git panel page: page header, panel rendering, tab navigation,
 * and content areas.
 *
 * Scenarios:
 *   1. Navigate to git page
 *   2. Verify page header and panel are visible
 *   3. Verify all four tabs (Changes, History, Branches, Graph) are rendered
 *   4. Switch between tabs and verify content updates
 *   5. Verify status view loads
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

test.describe('Git Integration', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.handlePinModal();
    // Navigate to Git page via direct route
    await dashboard.gotoPage('git');
  });

  test('should render the git page header', async () => {
    await dashboard.expectGitPageVisible();
    const header = dashboard.page.locator('.git-page-header h2');
    await expect(header).toBeVisible({ timeout: 5000 });
    const text = await header.textContent();
    expect(text).toContain('Git');
  });

  test('should render the git panel with all four tabs', async () => {
    await dashboard.expectGitPanelVisible();
    await dashboard.expectGitTabsVisible();
  });

  test('should have Changes tab active by default', async () => {
    await dashboard.expectGitTabActive('Changes');
  });

  test('should show tab content area after loading', async () => {
    await dashboard.expectGitContentVisible();
  });

  test('should switch to History tab and show content', async () => {
    await dashboard.clickGitTab('History');
    await dashboard.expectGitTabActive('History');
    await dashboard.expectGitContentVisible();
  });

  test('should switch to Branches tab and show content', async () => {
    await dashboard.clickGitTab('Branches');
    await dashboard.expectGitTabActive('Branches');
    await dashboard.expectGitContentVisible();
  });

  test('should switch to Graph tab and show content', async () => {
    await dashboard.clickGitTab('Graph');
    await dashboard.expectGitTabActive('Graph');
    await dashboard.expectGitContentVisible();
  });

  test('should return to Changes tab after navigating away', async () => {
    await dashboard.clickGitTab('History');
    await dashboard.expectGitTabActive('History');

    await dashboard.clickGitTab('Changes');
    await dashboard.expectGitTabActive('Changes');
  });

  test('should render git page subtitle', async () => {
    const subtitle = dashboard.page.locator('.git-page-header .page-subtitle');
    await expect(subtitle).toBeVisible({ timeout: 5000 });
    const text = await subtitle.textContent();
    expect(text?.length).toBeGreaterThan(0);
  });
});
