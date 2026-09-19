/**
 * UI-01 · 실제 BrowserRouter 접근성 gate
 * =========================================
 * GA-100 plan §UI-01 — hash URL(`#!`)을 제거하고 실제 BrowserRouter URL을
 * desktop/mobile viewport에서 연다.
 *
 * CR-08: 매트릭스에 "없는 경로(404)" 화면을 추가해 17 route로 확장했다.
 * (CR-07이 남긴 blocker — 404 화면이 접근성 게이트에 포함되지 않았던 문제 해소)
 *
 * 거짓 통과 방지 계약:
 *  - 각 case가 예상 pathname과 고유 route marker를 assertion한다.
 *    (route load 실패/마커 부재는 axe 결과와 **별도로** 실패한다)
 *  - critical/serious axe violation 0을 hard gate로 사용한다.
 *  - 결과 JSON과 screenshot이 route/viewport별로 저장된다
 *    (`testInfo.outputDir/a11y/<viewport>/<route>.json|.png`).
 *
 * 실패 원인 분리:
 *  - "route load 실패"   → route가 렌더링되지 않음 (marker assertion 실패)
 *  - "a11y gate 실패"    → route는 정상 로드, axe violation 존재
 *
 * 백엔드: 프로젝트 설정(webServer) 또는 실행 중인 AGK_BACKEND_URL을 사용한다.
 * 대부분의 route는 로컬 API 실패 시에도 고유 UI(shell + 페이지 헤더)를 렌더링하므로
 * a11y gate 자체는 백엔드 없이도 동작한다.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/* ─── 17개 route = 실제 16 route(App.tsx + PluginPanelRoutes) + 404 화면 ─── */

interface RouteCase {
  /** 실제 pathname — Browser History API로 직접 이동한다 (hash 불사용). */
  pathname: string;
  /** 사람이 읽는 route 이름 (결과/스냅샷 파일명). */
  name: string;
  /**
   * 고유 route marker — 이 route에서만 렌더링되는 요소.
   * 모호한 공용 셸 선택자 대신 페이지 고유 요소를 검증해 거짓 통과를 막는다.
   */
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
  /* CR-08: 셸 안에서 렌더되는 404 화면(CR-07)도 접근성 게이트 대상에 포함한다. */
  { pathname: '/cr08-unknown-route', name: 'not-found', marker: '[data-testid="cr07-not-found"]' },
];

/* ─── Viewport matrix ─── */

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
] as const;

type ViewportName = (typeof VIEWPORTS)[number]['name'];

/* ─── axe scan ─── */

interface ViolationRow {
  id: string;
  impact: string;
  help: string;
  nodes: number;
  targets: string[];
}

interface A11yReport {
  pathname: string;
  routeName: string;
  viewport: ViewportName;
  verifiedPathname: string;
  routeMarkerFound: boolean;
  passes: number;
  violations: ViolationRow[];
  criticalSerious: ViolationRow[];
}

async function scanAxe(page: Page): Promise<{ violations: ViolationRow[]; passes: number }> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'])
    .analyze();

  const violations: ViolationRow[] = results.violations.map(v => ({
    id: v.id,
    impact: v.impact ?? 'minor',
    help: v.help,
    nodes: v.nodes.length,
    targets: v.nodes.map(n => n.target.join(' ')),
  }));

  return { violations, passes: results.passes.length };
}

/* ─── UI-01 gate: 16 route × 2 viewport ─── */

for (const viewport of VIEWPORTS) {
  test.describe(`UI-01 route gate · ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    for (const route of ROUTES) {
      test(`[UI-01] ${route.pathname} · ${viewport.name} — marker + axe critical/serious 0`, async (
        { page },
        testInfo,
      ) => {
        test.setTimeout(60_000);

        const reportDir = path.join(testInfo.outputDir, 'a11y', viewport.name);
        await mkdir(reportDir, { recursive: true });

        /* 1. 실제 pathname으로 이동 (BrowserRouter — hash 불사용) */
        await page.goto(route.pathname);
        await page.waitForLoadState('domcontentloaded');

        /* 2. 거짓 통과 방지 — URL이 실제로 우리가 연 path인지 검증.
         *    서버가 index.html로 fallback한 경우에도 History API pathname은 유지된다. */
        const verifiedPathname = new URL(page.url()).pathname;
        expect
          .soft(verifiedPathname, `브라우저 URL pathname이 예상과 다릅니다 (route load 실패)`)
          .toBe(route.pathname);

        /* 3. 고유 route marker — route가 실제로 렌더링됐는지 검증.
         *    실패 시 "route load 실패"로 axe 게이트와 독립적으로 실패한다. */
        await expect(
          page.locator(route.marker).first(),
          `route marker 미발견 — ${route.pathname} 로드 실패`,
        ).toBeVisible({ timeout: 15_000 });

        /* 4. lazy chunk 정착 대기 후 axe scan */
        await page.waitForTimeout(1_000);
        const { violations, passes } = await scanAxe(page);

        const criticalSerious = violations.filter(
          v => v.impact === 'critical' || v.impact === 'serious',
        );

        /* 5. 결과 JSON + screenshot 저장 (route/viewport별) */
        const report: A11yReport = {
          pathname: route.pathname,
          routeName: route.name,
          viewport: viewport.name,
          verifiedPathname,
          routeMarkerFound: true,
          passes,
          violations,
          criticalSerious,
        };
        await writeFile(
          path.join(reportDir, `${route.name}.json`),
          JSON.stringify(report, null, 2),
          'utf8',
        );
        await page.screenshot({ path: path.join(reportDir, `${route.name}.png`), fullPage: true });

        /* 6. hard gate — critical/serious 0 */
        expect
          .soft(
            criticalSerious,
            `[${viewport.name}] ${route.pathname} critical/serious 위반 ${criticalSerious.length}건:\n` +
              criticalSerious.map(v => `  [${v.impact}] ${v.id}: ${v.help} (${v.nodes} nodes)`).join('\n'),
          )
          .toHaveLength(0);
      });
    }
  });
}

/* ─── 요약 test: gate 자체의 계약 고정 (스펙 회귀 방지) ─── */

test('[UI-01] gate 스펙 — 17 route × 2 viewport 매트릭스 고정', async () => {
  expect(ROUTES, 'UI-01은 실제 16 route + 404 화면 = 17개를 검사해야 한다').toHaveLength(17);
  const pathnames = new Set(ROUTES.map(r => r.pathname));
  expect(pathnames.size, 'route pathname 중복 없음').toBe(ROUTES.length);
  for (const route of ROUTES) {
    expect(route.marker, `${route.pathname} 마커 정의`).toBeTruthy();
    expect(route.marker.startsWith('#'), `hash 선택자 금지: ${route.pathname}`).toBe(false);
  }
  expect(VIEWPORTS.map(v => v.name)).toEqual(['desktop', 'mobile']);
});
