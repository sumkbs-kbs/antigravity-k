/**
 * UI-02 · 접근성 hard gate — 전 impact 위반 0
 * ============================================
 * GA-100 plan §UI-02 — UI-01(critical/serious 0)을 넘어 **모든 impact의 axe
 * 위반이 0**임을 hard gate로 고정한다. 위반 1건이라도 재발하면 이 스펙이
 * 실패한다 (heading-order/landmark/contrast/label 전부 포함).
 *
 * 백엔드: hermetic no-auth backend(명시적 dev 익명 허용)를 test마다 기동 —
 * 로컬 .env/credential 상태와 무관하게 결정적으로 동작한다.
 */
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

import { startNoAuthServer, type HermeticServer } from '../helpers/hermeticBackend';

process.env.AGK_SEC_DEV_NO_PIN_ALLOW = '1';

let server: HermeticServer;

test.beforeAll(async () => {
  server = await startNoAuthServer();
});

test.afterAll(async () => {
  await server.cleanup();
});

/* ─── 16개 실제 BrowserRouter route (UI-01 ROUTES와 동일 매트릭스) ─── */

interface RouteCase {
  pathname: string;
  name: string;
  marker: string;
}

const ROUTES: RouteCase[] = [
  { pathname: '/', name: 'chat', marker: '.agk-workspace' },
  { pathname: '/chat', name: 'chat-alias', marker: '.agk-workspace' },
  { pathname: '/studio', name: 'studio', marker: '.unsloth-studio-title' },
  { pathname: '/models', name: 'models', marker: '.hub-title' },
  { pathname: '/start', name: 'start', marker: '.start-title' },
  { pathname: '/wiki', name: 'wiki', marker: '.wiki-layout' },
  { pathname: '/agent', name: 'agent', marker: '.page-header-hero:has-text("에이전트 모니터링")' },
  { pathname: '/settings', name: 'settings', marker: '.page-header-hero:has-text("시스템 설정")' },
  { pathname: '/skills', name: 'skills', marker: '.page-header-hero:has-text("Skills Browser")' },
  { pathname: '/data-extraction', name: 'data-extraction', marker: '.empty-state-title:has-text("데이터 추출")' },
  { pathname: '/git', name: 'git', marker: 'h2:has-text("소스 제어")' },
  { pathname: '/history', name: 'history', marker: '.page-header-hero:has-text("파일 히스토리")' },
  { pathname: '/plugins', name: 'plugins', marker: '.page-header-hero:has-text("플러그인")' },
  { pathname: '/plugins/job-operations', name: 'plugins-job-operations', marker: '.job-operations-page' },
  { pathname: '/plugins/hello-world', name: 'plugins-hello-world', marker: '.hello-plugin-content' },
  { pathname: '/mutation', name: 'mutation', marker: '.page-header-hero:has-text("Mutation test history")' },
];

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
] as const;

type ViewportName = (typeof VIEWPORTS)[number]['name'];

async function scanAxe(page: Page): Promise<number> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'])
    .analyze();
  return results.violations.length;
}

for (const viewport of VIEWPORTS) {
  test.describe(`UI-02 hard gate · ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    for (const route of ROUTES) {
      test(`[UI-02] ${route.pathname} · ${viewport.name} — 전 impact axe 위반 0`, async ({ page }, testInfo) => {
        test.setTimeout(60_000);

        const reportDir = path.join(testInfo.outputDir, 'ui02', viewport.name);
        await mkdir(reportDir, { recursive: true });

        await page.goto(route.pathname);
        await page.waitForLoadState('domcontentloaded');

        /* 거짓 통과 방지 — route가 실제로 렌더링됐는지 먼저 검증 */
        await expect(
          page.locator(route.marker).first(),
          `route marker 미발견 — ${route.pathname} 로드 실패`,
        ).toBeVisible({ timeout: 15_000 });

        await page.waitForTimeout(1_000);
        const violationCount = await scanAxe(page);

        await writeFile(
          path.join(reportDir, `${route.name}.json`),
          JSON.stringify({ pathname: route.pathname, violationCount }, null, 2),
          'utf8',
        );

        /* hard gate — impact 불문 위반 0 */
        expect(
          violationCount,
          `[UI-02][${viewport.name}] ${route.pathname} axe 위반 ${violationCount}건 — 전 impact 0 정책 위반`,
        ).toBe(0);
      });
    }
  });
}

/* ─── 스펙 회귀 방지: 매트릭스 계약 고정 ─── */

test('[UI-02] gate 스펙 — UI-01과 동일 16 route 매트릭스 고정', async () => {
  expect(ROUTES).toHaveLength(16);
  const pathnames = new Set(ROUTES.map(r => r.pathname));
  expect(pathnames.size).toBe(ROUTES.length);
  expect(VIEWPORTS.map(v => v.name)).toEqual(['desktop', 'mobile']);
});
