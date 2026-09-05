import { test, expect } from '@playwright/test';
import * as path from 'path';

test('capture disclosure card healthy green state with 30 percent budget usage', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('http://127.0.0.1:5173/settings');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  // 1. Locate the SessionDisclosurePanel inside Settings section 04
  const panel = page.locator('.session-disclosure-panel');
  await expect(panel).toBeVisible({ timeout: 10000 });
  await expect(panel).toHaveClass(/level-healthy/);

  // 2. Verify banner text and icon
  const banner = panel.locator('.disclosure-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('세션 한도 — 여유');
  await expect(banner).toContainText('✅');

  // 3. Verify budget limit card (30% usage: .00 / .00)
  const budgetCard = panel.locator('.disclosure-limit-card').filter({ hasText: '일일 예산' });
  await expect(budgetCard).toBeVisible();
  await expect(budgetCard).toHaveClass(/level-healthy/);
  await expect(budgetCard.locator('.limit-usage')).toHaveText('$15.00 / $50.00');
  await expect(budgetCard.locator('.limit-level-badge')).toHaveText('✅ 여유');
  await expect(budgetCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '30');
  await expect(budgetCard.locator('.limit-message')).toContainText('일일 예산 여유가 충분합니다.');

  // 4. Verify action limit card (30% usage: 30 / 100 회)
  const actionCard = panel.locator('.disclosure-limit-card').filter({ hasText: '시간당 액션' });
  await expect(actionCard).toBeVisible();
  await expect(actionCard).toHaveClass(/level-healthy/);
  await expect(actionCard.locator('.limit-usage')).toHaveText('30 / 100 회');
  await expect(actionCard.locator('.limit-level-badge')).toHaveText('✅ 여유');
  await expect(actionCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '30');
  await expect(actionCard.locator('.limit-message')).toContainText('액션 한도 여유가 충분합니다.');

  // 5. Scroll panel into view and take focused screenshot
  await panel.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  const brainDir = '/Users/mr.k/.gemini/antigravity/brain/78f9bde0-c2cd-4614-a663-cb6b70f6deda';
  await panel.screenshot({ path: path.join(brainDir, 'artifacts_disclosure_healthy_panel.png') });
  await page.screenshot({ path: path.join(brainDir, 'artifacts_disclosure_healthy_full.png'), fullPage: true });

  // Also save to workspace root for consistency
  await panel.screenshot({ path: '../artifacts_disclosure_healthy_panel.png' });
  await page.screenshot({ path: '../artifacts_disclosure_healthy_full.png', fullPage: true });
});
