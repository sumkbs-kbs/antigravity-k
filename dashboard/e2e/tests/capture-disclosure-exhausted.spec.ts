import { test, expect } from '@playwright/test';
import * as path from 'path';

test('capture disclosure card exhausted state with time-until-reset countdown', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('http://127.0.0.1:5173/settings');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  // 1. Locate the SessionDisclosurePanel inside Settings
  const panel = page.locator('.session-disclosure-panel');
  await expect(panel).toBeVisible({ timeout: 10000 });
  await expect(panel).toHaveClass(/level-exhausted/);

  // 2. Verify banner text and icon
  const banner = panel.locator('.disclosure-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('세션 한도 — 소진');
  await expect(banner).toContainText('⛔');

  // 3. Verify budget limit card (100% usage: $50.00 / $50.00)
  const budgetCard = panel.locator('.disclosure-limit-card').filter({ hasText: '일일 예산' });
  await expect(budgetCard).toBeVisible();
  await expect(budgetCard).toHaveClass(/level-exhausted/);
  await expect(budgetCard.locator('.limit-usage')).toHaveText('$50.00 / $50.00');
  await expect(budgetCard.locator('.limit-level-badge')).toHaveText('⛔ 소진');
  await expect(budgetCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '100');

  // Verify time-until-reset countdown in budget message
  const budgetMessage = budgetCard.locator('.limit-message');
  await expect(budgetMessage).toContainText('일일 예산이 소진되었습니다 — 리셋까지');
  await expect(budgetMessage).toContainText('남음');
  const budgetCountdown = budgetCard.locator('[data-testid="reset-countdown"]');
  await expect(budgetCountdown).toBeVisible();
  expect(await budgetCountdown.textContent()).toMatch(/\d+시간\s+\d+분\s+\d+초|\d+분\s+\d+초/);

  // 4. Verify action limit card (100% usage: 100 / 100 회)
  const actionCard = panel.locator('.disclosure-limit-card').filter({ hasText: '시간당 액션' });
  await expect(actionCard).toBeVisible();
  await expect(actionCard).toHaveClass(/level-exhausted/);
  await expect(actionCard.locator('.limit-usage')).toHaveText('100 / 100 회');
  await expect(actionCard.locator('.limit-level-badge')).toHaveText('⛔ 소진');
  await expect(actionCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '100');

  // Verify time-until-reset countdown in action message
  const actionMessage = actionCard.locator('.limit-message');
  await expect(actionMessage).toContainText('시간당 액션 한도에 도달했습니다 — 리셋까지');
  await expect(actionMessage).toContainText('남음');
  const actionCountdown = actionCard.locator('[data-testid="reset-countdown"]');
  await expect(actionCountdown).toBeVisible();
  expect(await actionCountdown.textContent()).toMatch(/\d+시간\s+\d+분\s+\d+초|\d+분\s+\d+초/);

  // 5. Verify countdown is live ticking: wait 2 seconds and check that text changed
  const firstTick = await budgetCountdown.textContent();
  await page.waitForTimeout(2000);
  const secondTick = await budgetCountdown.textContent();
  expect(firstTick).not.toEqual(secondTick);

  // 6. Scroll panel into view and take focused screenshots
  await panel.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  const brainDir = '/Users/mr.k/.gemini/antigravity/brain/78f9bde0-c2cd-4614-a663-cb6b70f6deda';
  await panel.screenshot({ path: path.join(brainDir, 'artifacts_disclosure_exhausted_countdown_panel.png') });
  await page.screenshot({ path: path.join(brainDir, 'artifacts_disclosure_exhausted_countdown_full.png'), fullPage: true });

  // Also save in workspace root for easy reference
  await panel.screenshot({ path: '../artifacts_disclosure_exhausted_countdown_panel.png' });
  await page.screenshot({ path: '../artifacts_disclosure_exhausted_countdown_full.png', fullPage: true });
});
