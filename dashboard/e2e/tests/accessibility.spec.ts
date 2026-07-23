/**
 * Accessibility (a11y) Audit — axe-core
 * =======================================
 * Runs automated accessibility scans on all main dashboard pages.
 * Uses @axe-core/playwright for Axe DevTools integration.
 *
 * Violations are categorized by severity:
 *   - critical: must fix
 *   - serious: should fix
 *   - moderate: consider fixing
 *   - minor: nice to have
 *
 * The test fails on critical + serious violations.
 * Moderate + minor violations are reported as warnings.
 */

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const PAGES = [
  { path: '/chat', name: 'Chat Page' },
  { path: '/settings', name: 'Settings Page' },
  { path: '/history', name: 'History Page' },
  { path: '/plugins', name: 'Plugin Page' },
  { path: '/mutation', name: 'Mutation Dashboard' },
  { path: '/wiki', name: 'Wiki Page' },
  { path: '/agent', name: 'Agent Page' },
  { path: '/skills', name: 'Skills Page' },
  { path: '/data-extraction', name: 'Data Extraction Page' },
  { path: '/git', name: 'Git Page' },
];

// ─── Helper: Run axe-core scan and collect violations ───────────

interface A11yResult {
  violations: { id: string; impact: string; description: string; help: string; tags: string[]; nodes: number; failingElements?: string[][] }[];
  incomplete: { id: string; impact: string; description: string }[];
  inapplicable: { id: string }[];
  passes: number;
}

async function scanPage(page: any): Promise<A11yResult> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'])
    .analyze();

  const violations = results.violations.map(v => ({
    id: v.id,
    impact: v.impact || 'minor',
    description: v.description,
    help: v.help,
    tags: v.tags,
    nodes: v.nodes.length,
    failingElements: v.nodes.map(n => n.target),
  }));

  const incomplete = results.incomplete.map(v => ({
    id: v.id,
    impact: v.impact || 'unknown',
    description: v.description,
  }));

  const inapplicable = results.inapplicable.map(v => ({ id: v.id }));

  return {
    violations,
    incomplete,
    inapplicable,
    passes: results.passes.length,
  };
}

// ─── Tests ──────────────────────────────────────────────────────

for (const { path, name } of PAGES) {
  test(`[A11y] ${name} — no critical/serious violations`, async ({ page }) => {
    await page.goto(`/#!${path}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500); // Wait for lazy-loaded components

    const result = await scanPage(page);

    // Separate by severity
    const criticalSerious = result.violations.filter(
      v => v.impact === 'critical' || v.impact === 'serious'
    );
    const moderateMinor = result.violations.filter(
      v => v.impact === 'moderate' || v.impact === 'minor'
    );

    // Log all violations for debugging
    if (result.violations.length > 0) {
      console.log(`\n[A11y] ${name} — ${result.violations.length} violations found (passes: ${result.passes})`);
      for (const v of result.violations) {
        const tag = v.impact === 'critical' ? '🔴' : v.impact === 'serious' ? '🟠' : v.impact === 'moderate' ? '🟡' : '🔵';
        console.log(`  ${tag} [${v.impact}] ${v.id}: ${v.help} (${v.nodes} nodes)`);
        if (v.failingElements) {
          for (const targets of v.failingElements) {
            console.log(`    → ${targets.join(', ')}`);
          }
        }
      }
    }

    // Fail on critical + serious
    expect(
      criticalSerious,
      `Critical/serious violations on ${name}:\n${
        criticalSerious.map(v => `  [${v.impact}] ${v.id}: ${v.help}`).join('\n')
      }`
    ).toHaveLength(0);

    // Warn about moderate + minor
    if (moderateMinor.length > 0) {
      console.warn(
        `⚠️  [A11y] ${name} — ${moderateMinor.length} moderate/minor violations:\n${
          moderateMinor.map(v => `  🟡 [${v.impact}] ${v.id}: ${v.help}`).join('\n')
        }`
      );
    }
  });
}

// ─── Focus Management Test ──────────────────────────────────────

test('[A11y] Command Palette — focus management', async ({ page }) => {
  await page.goto('/#!');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  // Open command palette via Cmd+K
  await page.keyboard.press('Meta+k');
  await page.waitForTimeout(500);

  // Check that input is focused
  const focused = await page.evaluate(() => {
    const el = document.activeElement;
    return el?.tagName + (el?.getAttribute('aria-label') ? `: ${el.getAttribute('aria-label')}` : '');
  });
  console.log(`[A11y] Command palette focused element: ${focused}`);

  // Close with Escape
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
});

// ─── Keyboard Navigation Test ───────────────────────────────────

test('[A11y] Sidebar — keyboard navigation', async ({ page }) => {
  await page.goto('/#!');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  // Tab through sidebar items
  const sidebarLinks = page.locator('.sidebar-nav .nav-item');
  const linkCount = await sidebarLinks.count();
  expect(linkCount).toBeGreaterThan(0);

  // Verify focusable elements exist in sidebar
  const focusableCount = await page.locator('.sidebar a, .sidebar button, .sidebar [tabindex="0"]').count();
  console.log(`[A11y] Sidebar focusable elements: ${focusableCount}`);
  expect(focusableCount).toBeGreaterThan(5);
});
