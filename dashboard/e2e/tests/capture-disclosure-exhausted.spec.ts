import { test, expect } from '@playwright/test';
import * as path from 'path';
import { mkdirSync } from 'fs';

/**
 * CR-14 F-47 → attempt-035: Vite :5173 하드코드를 제거하고 playwright baseURL
 * (AGK_BACKEND_URL = hermetic ambient 서버) + AGK_SEED_LEVEL=exhausted 로 소유한다.
 * 시드는 `scripts/run_dashboard_e2e_ambient.py` 의 disclosure 단계가 넣는다.
 */
test('capture disclosure card exhausted state with time-until-reset countdown', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/settings');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  const panel = page.locator('.session-disclosure-panel');
  await expect(panel).toBeVisible({ timeout: 10000 });
  await expect(panel).toHaveClass(/level-exhausted/);

  const banner = panel.locator('.disclosure-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('세션 한도 — 소진');
  await expect(banner).toContainText('⛔');

  const budgetCard = panel.locator('.disclosure-limit-card').filter({ hasText: '일일 예산' });
  await expect(budgetCard).toBeVisible();
  await expect(budgetCard).toHaveClass(/level-exhausted/);
  await expect(budgetCard.locator('.limit-usage')).toHaveText('$50.00 / $50.00');
  await expect(budgetCard.locator('.limit-level-badge')).toHaveText('⛔ 소진');
  await expect(budgetCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '100');

  const budgetMessage = budgetCard.locator('.limit-message');
  await expect(budgetMessage).toContainText('일일 예산이 소진되었습니다 — 리셋까지');
  await expect(budgetMessage).toContainText('남음');
  const budgetCountdown = budgetCard.locator('[data-testid="reset-countdown"]');
  await expect(budgetCountdown).toBeVisible();
  expect(await budgetCountdown.textContent()).toMatch(/\d+시간\s+\d+분\s+\d+초|\d+분\s+\d+초/);

  const actionCard = panel.locator('.disclosure-limit-card').filter({ hasText: '시간당 액션' });
  await expect(actionCard).toBeVisible();
  await expect(actionCard).toHaveClass(/level-exhausted/);
  await expect(actionCard.locator('.limit-usage')).toHaveText('100 / 100 회');
  await expect(actionCard.locator('.limit-level-badge')).toHaveText('⛔ 소진');
  await expect(actionCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '100');

  const actionMessage = actionCard.locator('.limit-message');
  await expect(actionMessage).toContainText('시간당 액션 한도에 도달했습니다 — 리셋까지');
  await expect(actionMessage).toContainText('남음');
  const actionCountdown = actionCard.locator('[data-testid="reset-countdown"]');
  await expect(actionCountdown).toBeVisible();
  expect(await actionCountdown.textContent()).toMatch(/\d+시간\s+\d+분\s+\d+초|\d+분\s+\d+초/);

  const firstTick = await budgetCountdown.textContent();
  await page.waitForTimeout(2000);
  const secondTick = await budgetCountdown.textContent();
  expect(firstTick).not.toEqual(secondTick);

  await panel.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  const outDir = process.env.VISUAL_ARTIFACT_DIR
    ?? path.join(process.cwd(), 'test-results', 'disclosure-capture');
  mkdirSync(outDir, { recursive: true });
  await panel.screenshot({ path: path.join(outDir, 'artifacts_disclosure_exhausted_countdown_panel.png') });
  await page.screenshot({ path: path.join(outDir, 'artifacts_disclosure_exhausted_countdown_full.png'), fullPage: true });
});
