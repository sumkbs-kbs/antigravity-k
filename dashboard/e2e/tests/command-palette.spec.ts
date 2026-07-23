/**
 * Command Palette E2E Test
 * ========================
 * Verifies the Cmd+K command palette is functional and searchable.
 *
 * Based on "Phase 2: Command Palette" from test_process.md.
 * Tests: open palette → search → verify commands → close
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

test.describe('Command Palette', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.handlePinModal();
  });

  test('should open command palette and search for goal', async () => {
    await dashboard.openCommandPalette();
    await dashboard.searchCommand('goal');
    await dashboard.expectCommandItem('goal');
  });

  test('should open command palette and search for self', async () => {
    await dashboard.openCommandPalette();
    await dashboard.searchCommand('self');
    await dashboard.expectCommandItem('self');
  });

  test('should open command palette and search for benchmark', async () => {
    await dashboard.openCommandPalette();
    await dashboard.searchCommand('benchmark');
    await dashboard.expectCommandItem('benchmark');
  });

  test('should close command palette on Escape', async () => {
    await dashboard.openCommandPalette();
    await dashboard.closeCommandPalette();
    const overlayStillVisible = await dashboard.commandPaletteOverlay.isVisible().catch(() => false);
    expect(overlayStillVisible).toBeFalsy();
  });
});
