/**
 * CR-06 · 설정 상태가 서버의 진실을 반영하는지 실제 브라우저에서 확인한다.
 * =====================================================================
 * 발견 F02: 초기 GET이 실패해도 화면이 기본값 폼을 정상 설정처럼 보여주고
 * 저장까지 허용했다. 이 스펙은
 *
 *   1) 초기 GET 실패(500) → 오류 상태 + 재시도, 저장 버튼 없음
 *   2) 초기 GET timeout(abort) → 같은 오류 상태, 재시도는 실제 서버로 복구
 *   3) 저장 실패(500) → 비밀 아닌 입력 유지 + 재시도 가능, 성공 주장 없음
 *   4) 연속 클릭 3회 → 실제 요청 1건
 *   5) 서버가 0을 말하면 화면도 0(하드코딩 기본값으로 대체 금지)
 *   6) 성공 경로는 실제 서버 — 서버 강제 한도가 화면에 그대로 보인다
 *
 * 을 확인한다. 1/2/3/4는 실제 서버를 상대로 실패만 **결정적으로 주입**하고,
 * 6은 주입 없이 실제 서버만 쓴다. 5는 서버 응답을 주입해 0값 경로를 고정한다.
 */
import { expect, test, type Page } from '@playwright/test';
import { startBackendServer, type HermeticServer } from '../helpers/hermeticBackend';

/* SEC-01 fail-closed 정책에서 익명 loopback 부팅은 명시적 dev 허용이 필요하다. */
process.env.AGK_SEC_DEV_NO_PIN_ALLOW = '1';

const BLANKED_PROVIDER_KEYS: Record<string, string> = {
  OPENROUTER_API_KEY: '',
  NVIDIA_API_KEY: '',
  OPENAI_API_KEY: '',
  GEMINI_API_KEY: '',
  ZAI_API_KEY: '',
  ANTHROPIC_API_KEY: '',
};

function startSettingsServer(): Promise<HermeticServer> {
  return startBackendServer(BLANKED_PROVIDER_KEYS);
}

const FAKE_KEY = 'sk-cr06-e2e-fake-7c31d9-never-a-real-key';

const LOAD_ERROR = '[data-testid="settings-load-error"]';
const RETRY = '[data-testid="settings-retry"]';
const SAVE = '[data-testid="settings-save"]';
const SAVE_ERROR = '[data-testid="settings-save-error"]';

async function gotoSettings(page: Page): Promise<void> {
  await page.goto('/settings');
  await page.waitForLoadState('domcontentloaded');
}

test('initial load failure shows an error state instead of a saveable default form', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  await page.route('**/api/settings', route =>
    route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"boom"}' }),
  );
  try {
    await gotoSettings(page);

    await expect(page.locator(LOAD_ERROR)).toBeVisible({ timeout: 20_000 });
    await expect(page.locator(RETRY)).toBeVisible();
    // 서버의 진실을 모르는 상태 — 저장 경로가 화면에 존재하지 않는다.
    await expect(page.locator(SAVE)).toHaveCount(0);
    // 서버가 준 적 없는 기본값(50/100)이 입력된 폼도 없다.
    await expect(page.locator('input[value="50"]')).toHaveCount(0);
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('a load timeout is surfaced and the retry recovers against the real server', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  let failNext = true;
  await page.route('**/api/settings', route => {
    if (failNext) {
      failNext = false;
      return route.abort('timedout');
    }
    return route.continue();
  });
  try {
    await gotoSettings(page);
    await expect(page.locator(LOAD_ERROR)).toBeVisible({ timeout: 20_000 });

    // 재시도는 실제 서버로 가서 서버 값을 채운다.
    await page.locator(RETRY).click();
    await expect(page.locator(LOAD_ERROR)).toHaveCount(0, { timeout: 20_000 });
    await expect(page.locator(SAVE)).toBeEnabled();

    const settings = (await (await page.request.get('/api/settings')).json()) as {
      settings: { model?: { name?: string } };
    };
    await expect(page.getByTestId('settings-default-model')).toHaveValue(
      settings.settings.model?.name ?? '',
    );
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('a failed save keeps non-secret input and never claims success', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  await page.route('**/api/settings/env', route =>
    route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"boom"}' }),
  );
  try {
    await gotoSettings(page);
    await expect(page.locator(SAVE)).toBeVisible({ timeout: 20_000 });

    await page.getByTestId('settings-default-model').fill('e2e-edited-model');
    await page.getByTestId('api-key-input-OPENAI_API_KEY').fill(FAKE_KEY);
    await page.locator(SAVE).click();

    await expect(page.locator(SAVE_ERROR)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/저장 완료/)).toHaveCount(0);
    // 비밀 아닌 입력은 유지되고, 다시 시도할 수 있다.
    await expect(page.getByTestId('settings-default-model')).toHaveValue('e2e-edited-model');
    await expect(page.getByTestId('api-key-input-OPENAI_API_KEY')).toHaveValue(FAKE_KEY);
    await expect(page.locator(SAVE)).toBeEnabled();
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('three rapid clicks produce exactly one save request', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const savePosts: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().includes('/api/settings/env')) {
      savePosts.push(request.url());
    }
  });
  // 요청을 붙잡아 두어 세 번의 클릭이 모두 진행 중 창 안에서 일어나게 한다.
  await page.route('**/api/settings/env', async route => {
    await new Promise(resolve => setTimeout(resolve, 1_000));
    await route.continue();
  });
  try {
    await gotoSettings(page);
    await expect(page.locator(SAVE)).toBeVisible({ timeout: 20_000 });
    await page.getByTestId('api-key-input-OPENAI_API_KEY').fill(FAKE_KEY);

    // 같은 tick에 3번 클릭 — 첫 클릭의 진행 중 표시(ref)가 나머지를 막아야 한다.
    await page.locator(SAVE).evaluate((element: HTMLElement) => {
      element.click();
      element.click();
      element.click();
    });

    await expect(page.getByText(/저장 완료/)).toBeVisible({ timeout: 30_000 });
    expect(savePosts).toHaveLength(1);
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('a server-reported zero cost is shown and preserved, not replaced by a default', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const zeroSettings = {
    settings: {
      model: { name: 'e2e-zero-model' },
      cost: { daily_budget_usd: 0, hourly_action_limit: 0 },
      api_keys_configured: { OPENAI_API_KEY: false },
    },
  };
  await page.route('**/api/settings', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(zeroSettings) }),
  );
  await page.route('**/api/settings/env', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, updated: 1, message: 'ok' }),
    }),
  );
  try {
    await gotoSettings(page);
    await expect(page.locator(SAVE)).toBeVisible({ timeout: 20_000 });

    await expect(page.getByTestId('settings-daily-budget')).toHaveValue('0');
    await expect(page.getByTestId('settings-hourly-limit')).toHaveValue('0');
    await expect(page.getByTestId('settings-server-cost')).toContainText('0');

    await page.getByTestId('api-key-input-OPENAI_API_KEY').fill(FAKE_KEY);
    await page.locator(SAVE).click();
    await expect(page.getByText(/저장 완료/)).toBeVisible({ timeout: 20_000 });

    const stored = await page.evaluate(() =>
      JSON.parse(window.localStorage.getItem('agk_user_settings:v1') ?? '{}') as Record<string, unknown>,
    );
    expect(stored.daily_budget_usd).toBe('0');
    expect(stored.hourly_action_limit).toBe('0');
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('the success path uses the real server and shows its enforced cost limits', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  try {
    await gotoSettings(page);
    await expect(page.locator(SAVE)).toBeVisible({ timeout: 20_000 });

    const settings = (await (await page.request.get('/api/settings')).json()) as {
      settings: { cost?: { daily_budget_usd?: number | string; hourly_action_limit?: number | string } };
    };
    const daily = String(settings.settings.cost?.daily_budget_usd ?? '');
    const hourly = String(settings.settings.cost?.hourly_action_limit ?? '');
    expect(daily).not.toBe('');
    expect(hourly).not.toBe('');
    await expect(page.getByTestId('settings-server-cost')).toContainText(daily);
    await expect(page.getByTestId('settings-server-cost')).toContainText(hourly);

    await page.getByTestId('api-key-input-OPENAI_API_KEY').fill(FAKE_KEY);
    await page.locator(SAVE).click();
    await expect(page.getByText(/저장 완료/)).toBeVisible({ timeout: 20_000 });
    // 저장 후 재조회한 서버 값이 그대로 남아 있다(오류 복구 후 재조회 경로).
    await expect(page.getByTestId('settings-server-cost')).toContainText(daily);
  } finally {
    await context.close();
    await server.cleanup();
  }
});
