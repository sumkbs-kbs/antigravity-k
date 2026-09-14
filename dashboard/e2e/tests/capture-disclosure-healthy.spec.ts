import { test, expect } from '@playwright/test';
import * as path from 'path';
import { mkdirSync } from 'fs';

/**
 * CR-14 F-47 → attempt-035: Vite :5173 하드코드를 제거하고 playwright baseURL
 * (AGK_BACKEND_URL = hermetic ambient 서버) + AGK_SEED_LEVEL=healthy 로 소유한다.
 * 시드는 `scripts/run_dashboard_e2e_ambient.py` 의 disclosure 단계가 넣는다.
 */
test('capture disclosure card healthy green state with 30 percent budget usage', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/settings');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  const panel = page.locator('.session-disclosure-panel');
  await expect(panel).toBeVisible({ timeout: 10000 });
  await expect(panel).toHaveClass(/level-healthy/);

  const banner = panel.locator('.disclosure-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('세션 한도 — 여유');
  await expect(banner).toContainText('✅');

  const budgetCard = panel.locator('.disclosure-limit-card').filter({ hasText: '일일 예산' });
  await expect(budgetCard).toBeVisible();
  await expect(budgetCard).toHaveClass(/level-healthy/);
  await expect(budgetCard.locator('.limit-usage')).toHaveText('$15.00 / $50.00');
  await expect(budgetCard.locator('.limit-level-badge')).toHaveText('✅ 여유');
  await expect(budgetCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '30');
  await expect(budgetCard.locator('.limit-message')).toContainText('일일 예산 여유가 충분합니다.');

  const actionCard = panel.locator('.disclosure-limit-card').filter({ hasText: '시간당 액션' });
  await expect(actionCard).toBeVisible();
  await expect(actionCard).toHaveClass(/level-healthy/);
  await expect(actionCard.locator('.limit-usage')).toHaveText('30 / 100 회');
  await expect(actionCard.locator('.limit-level-badge')).toHaveText('✅ 여유');
  await expect(actionCard.locator('.limit-gauge')).toHaveAttribute('aria-valuenow', '30');
  await expect(actionCard.locator('.limit-message')).toContainText('액션 한도 여유가 충분합니다.');

  await panel.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  const outDir = process.env.VISUAL_ARTIFACT_DIR
    ?? path.join(process.cwd(), 'test-results', 'disclosure-capture');
  mkdirSync(outDir, { recursive: true });
  await panel.screenshot({ path: path.join(outDir, 'artifacts_disclosure_healthy_panel.png') });
  await page.screenshot({ path: path.join(outDir, 'artifacts_disclosure_healthy_full.png'), fullPage: true });
});
