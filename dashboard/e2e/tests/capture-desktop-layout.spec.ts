import { test, expect } from '@playwright/test';

test('capture desktop layout screenshot', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  // Take full desktop screenshot
  await page.screenshot({ path: '../artifacts_capture_desktop.png', fullPage: true });
});
