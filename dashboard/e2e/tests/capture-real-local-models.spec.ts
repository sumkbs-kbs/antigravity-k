import { test, expect } from '@playwright/test';

test('capture ModelHubPage with real unsloth and local models', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/models');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  // Verify Unsloth model is present in the grid
  const unslothCard = page.locator('.hub-card').filter({ hasText: 'orpheus-3b-0.1-ft-UD-Q4_K_XL' });
  await expect(unslothCard).toBeVisible();

  // Verify green running badge or click activate
  const runningBadge = unslothCard.locator('text=실행 중');
  await expect(runningBadge).toBeVisible();

  // Take screenshot of ModelHubPage
  await page.screenshot({ path: '../artifacts_real_local_models_hub.png', fullPage: true });
});

test('capture ChatPage model selector with real running and unsloth models', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);

  // Click the model selector trigger button
  const modelBtn = page.getByRole('button', { name: '모델 선택' });
  await expect(modelBtn).toBeVisible();
  await modelBtn.click();
  await page.waitForTimeout(800);

  // Take screenshot with model selection popover open
  await page.screenshot({ path: '../artifacts_real_local_models_chat.png', fullPage: true });
});

