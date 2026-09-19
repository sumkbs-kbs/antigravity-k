import { test, expect } from '@playwright/test';

test('capture model selection popover with real local models', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  // Click the model selector trigger button
  const modelBtn = page.getByRole('button', { name: '모델 선택' });
  await expect(modelBtn).toBeVisible();
  await modelBtn.click();
  await page.waitForTimeout(500);

  // Take screenshot with model selection popover open
  await page.screenshot({ path: '../artifacts_capture_model_selection.png', fullPage: true });
});
