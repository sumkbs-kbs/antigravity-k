/**
 * UI-02 · 위반 인벤토리 스펙
 * ==========================
 * GA-100 plan §UI-02 — UI-01(critical/serious 0)을 넘어 **모든 impact 위반을
 * 인벤토리화**한다. hard gate는 아니고 JSON 리포트를 남겨 수정 대상을 확정한다.
 *
 * 실행: npx playwright test e2e/tests/accessibility-inventory.spec.ts
 */
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const OUT = path.resolve(process.cwd(), '.tmp/ui02-inventory');

const ROUTES = [
  { pathname: '/', name: 'chat' },
  { pathname: '/studio', name: 'studio' },
  { pathname: '/models', name: 'models' },
  { pathname: '/start', name: 'start' },
  { pathname: '/wiki', name: 'wiki' },
  { pathname: '/agent', name: 'agent' },
  { pathname: '/settings', name: 'settings' },
  { pathname: '/skills', name: 'skills' },
  { pathname: '/data-extraction', name: 'data-extraction' },
  { pathname: '/git', name: 'git' },
  { pathname: '/history', name: 'history' },
  { pathname: '/plugins', name: 'plugins' },
  { pathname: '/plugins/job-operations', name: 'plugins-job-operations' },
  { pathname: '/plugins/hello-world', name: 'plugins-hello-world' },
  { pathname: '/mutation', name: 'mutation' },
];

for (const viewport of [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
] as const) {
  test.describe(`inventory · ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    for (const route of ROUTES) {
      test(`${route.pathname} · ${viewport.name}`, async ({ page }, testInfo) => {
        test.setTimeout(60_000);
        await page.goto(route.pathname);
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1_000);

        const results = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'])
          .analyze();

        const summary = results.violations.map(v => ({
          id: v.id,
          impact: v.impact ?? 'minor',
          help: v.help,
          nodes: v.nodes.length,
          targets: v.nodes.slice(0, 6).map(n => n.target.join(' ')),
        }));
        await mkdir(path.join(OUT, viewport.name), { recursive: true });
        await writeFile(
          path.join(OUT, viewport.name, `${route.name}.json`),
          JSON.stringify({ pathname: route.pathname, violations: summary }, null, 2),
          'utf8',
        );
        // 인벤토리 자체는 항상 통과 — 리포트가 산출물
        expect(summary).toBeDefined();
      });
    }
  });
}
