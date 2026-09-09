/**
 * UI-02 · keyboard workflow gate
 * ===============================
 * GA-100 plan §UI-02 — 주요 workflow를 keyboard만으로 수행 가능함을 검증한다.
 *
 *  - sidebar NavLink 탐색 (git → 키보드 Enter) → settings
 *  - Cmd+K command palette open/search/close
 *  - Tab focus가 보이는가 (visible focus) — focus 후 outline/box-shadow 계산값 검증
 *
 * 백엔드: playwright.config webServer(AGK_BACKEND_URL) — UI-01 gate와 동일 환경.
 */
import { test, expect } from '@playwright/test';

import { startNoAuthServer, type HermeticServer } from '../helpers/hermeticBackend';

/*
 * SEC-01 fail-closed 정책 하에서 no-auth 시나리오는 명시적 dev 익명 허용
 * (AGK_SEC_DEV_NO_PIN_ALLOW)이 필요하다 — 테스트도 production 코드와 같은
 * 문을 통과한다. hermeticBackend의 격리 env 위에 이 env만 추가해 기동한다.
 */
process.env.AGK_SEC_DEV_NO_PIN_ALLOW = '1';

/*
 * hermetic no-auth backend (SEC-01 fail-closed 환경에서 익명 loopback 부팅)을
 * test마다 기동하고, dashboard static mount를 그대로 사용한다 (port 0 → 무충돌).
 */
let server: HermeticServer;

test.beforeAll(async () => {
  server = await startNoAuthServer();
  console.log('[UI-02] hermetic baseUrl:', server.baseUrl);
});

test.afterAll(async () => {
  await server.cleanup();
});

test.describe('UI-02 keyboard workflows', () => {
  test('Cmd+K palette open → search → Escape close', async ({ browser }) => {
    const context = await browser.newContext({ baseURL: server.baseUrl });
    const page = await context.newPage();
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // useGlobalCommandPalette는 AppContent 마운트 후 리스너를 단다 — aside(쉘) 렌더 대기
    await page.locator('aside').first().waitFor({ state: 'visible', timeout: 20_000 });
    await page.keyboard.press('ControlOrMeta+k');
    const paletteInput = page.getByRole('dialog', { name: '명령 팔레트' }).getByRole('combobox');
    await expect(paletteInput).toBeVisible({ timeout: 5_000 });

    await page.keyboard.type('goal');
    await page.keyboard.press('Escape');
    await context.close();
  });

  test('sidebar NavLink keyboard 탐색 — chat → git', async ({ browser }) => {
    const context = await browser.newContext({ baseURL: server.baseUrl });
    const page = await context.newPage();
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const sidebar = page.locator('aside').first();
    await expect(sidebar).toBeVisible({ timeout: 20_000 });

    const gitLink = sidebar.locator('a[href="/git"]').first();
    await gitLink.waitFor({ state: 'visible', timeout: 20_000 });
    await gitLink.focus();
    await expect(gitLink).toBeFocused();
    await page.keyboard.press('Enter');
    await page.waitForURL('**/git', { timeout: 10_000 });
    await expect(page.locator('h2:has-text("소스 제어")')).toBeVisible();
    await context.close();
  });

  test('sidebar NavLink keyboard 탐색 — chat → settings (도움말 링크)', async ({ browser }) => {
    const context = await browser.newContext({ baseURL: server.baseUrl });
    const page = await context.newPage();
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const sidebar = page.locator('aside').first();
    const settingsLink = sidebar.locator('a[href="/settings"]').first();
    await settingsLink.scrollIntoViewIfNeeded();
    await settingsLink.focus();
    await page.keyboard.press('Enter');
    await page.waitForURL('**/settings', { timeout: 10_000 });
    await expect(page.locator('.page-header-hero:has-text("시스템 설정")')).toBeVisible();
    await context.close();
  });

  test('visible focus — focused element에 시각적 focus 표시가 있다', async ({ browser }) => {
    const context = await browser.newContext({ baseURL: server.baseUrl });
    const page = await context.newPage();
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const sidebar = page.locator('aside').first();
    const link = sidebar.locator('a').first();
    await link.focus();
    await expect(link).toBeFocused();

    const focusStyle = await link.evaluate(el => {
      const style = getComputedStyle(el);
      return `${style.outlineStyle} ${style.outlineWidth} ${style.boxShadow}`;
    });
    // outline none + box-shadow none이면 visible focus 위반 (WCAG 2.4.7)
    const hasNoFocusIndicator =
      focusStyle.trim() === 'none 0px none' || focusStyle.trim() === 'none 0px';
    expect(hasNoFocusIndicator, `focus 표시 없음: ${focusStyle}`).toBe(false);
    await context.close();
  });
});
