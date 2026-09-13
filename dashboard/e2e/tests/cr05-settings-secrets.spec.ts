/**
 * CR-05 · 설정 화면의 API 키 브라우저 영속 제거 (실제 브라우저)
 * ==========================================================
 * 발견 F01: 설정 화면이 API 키를 localStorage에 원문 저장했다. 이 스펙은
 * 모듈 단위가 아니라 **실제 chromium + 실제 서버**에서 그 키가
 *
 *   1) 저장 후에도 어떤 브라우저 영속 저장소(localStorage/sessionStorage/
 *      IndexedDB)에도 남지 않고,
 *   2) 재로드 후 입력란이 비어 있으며 상태는 서버의 `configured`에서 오고,
 *   3) 페이지를 떠나면 입력값이 사라지고,
 *   4) 기존 legacy 키는 앱 시작 시 정화된다
 *
 * 는 것을 확인한다. 서버 `.env`는 `AGK_ENV_FILE`로 격리된 임시 파일을 쓰므로
 * 개발자의 실제 `.env`는 건드리지 않는다(hermeticBackend가 설정한다).
 */
import { expect, test, type Page } from '@playwright/test';
import { startBackendServer, type HermeticServer } from '../helpers/hermeticBackend';

/*
 * SEC-01 fail-closed 정책에서 익명 loopback 부팅은 명시적 dev 허용이 필요하다
 * (keyboard-workflows 스펙과 같은 문을 통과한다). 이 env가 없으면 앱이 PIN
 * 모달을 띄워 설정 화면에 도달하지 못한다.
 */
process.env.AGK_SEC_DEV_NO_PIN_ALLOW = '1';

/*
 * 개발자 셸에 provider 키가 export되어 있으면 '설정됨' 상태가 처음부터 참이 되어
 * 이 시나리오가 아무것도 검증하지 못한다. 모든 provider 키를 빈 값으로 고정해
 * "내가 저장한 키만" 관찰한다.
 */
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

const FAKE_KEY = 'sk-cr05-e2e-fake-2b8d47-never-a-real-key';
const LEGACY_SECRET = 'sk-cr05-e2e-legacy-91af03-should-be-purged';

/** 브라우저에 실제로 영속된 모든 텍스트를 모은다(localStorage/sessionStorage/IndexedDB). */
async function collectPersistedText(page: Page): Promise<string> {
  return page.evaluate(async () => {
    const chunks: string[] = [];
    try {
      for (let i = 0; i < window.localStorage.length; i += 1) {
        const key = window.localStorage.key(i);
        if (key === null) continue;
        chunks.push(`${key}=${window.localStorage.getItem(key) ?? ''}`);
      }
    } catch { /* storage denied */ }
    try {
      for (let i = 0; i < window.sessionStorage.length; i += 1) {
        const key = window.sessionStorage.key(i);
        if (key === null) continue;
        chunks.push(`${key}=${window.sessionStorage.getItem(key) ?? ''}`);
      }
    } catch { /* storage denied */ }

    const openDatabase = (name: string): Promise<IDBDatabase> => new Promise((resolve, reject) => {
      const request = window.indexedDB.open(name);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    try {
      const databases = typeof window.indexedDB.databases === 'function'
        ? await window.indexedDB.databases()
        : [];
      for (const info of databases) {
        if (!info.name) continue;
        const database = await openDatabase(info.name);
        try {
          for (const storeName of Array.from(database.objectStoreNames)) {
            const rows = await new Promise<unknown[]>((resolve, reject) => {
              const request = database.transaction(storeName, 'readonly').objectStore(storeName).getAll();
              request.onsuccess = () => resolve(request.result);
              request.onerror = () => reject(request.error);
            });
            chunks.push(`${info.name}/${storeName}:${JSON.stringify(rows)}`);
          }
        } finally {
          database.close();
        }
      }
    } catch { /* indexeddb unavailable */ }

    return chunks.join('\n');
  });
}

async function gotoSettings(page: Page): Promise<void> {
  await page.goto('/settings');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByRole('heading', { name: '시스템 설정' })).toBeVisible({ timeout: 15_000 });
}

test('typed API key never persists in the browser and is cleared after save/reload', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  try {
    await gotoSettings(page);
    const input = page.getByTestId('api-key-input-OPENAI_API_KEY');
    // 아직 아무것도 설정하지 않았다 — 시작 상태가 '미설정'임을 먼저 고정한다.
    await expect(page.getByTestId('api-key-delete-OPENAI_API_KEY')).toHaveCount(0);
    await input.fill(FAKE_KEY);
    await expect(input).toHaveValue(FAKE_KEY);

    await page.getByRole('button', { name: /설정 저장/ }).click();
    await expect(page.getByText(/저장 완료/)).toBeVisible({ timeout: 20_000 });

    // 1) 어떤 브라우저 영속 저장소에도 키가 없다.
    expect(await collectPersistedText(page)).not.toContain(FAKE_KEY);
    // 입력값과 삭제 표시는 성공 저장 후 메모리에서 지워진다.
    await expect(input).toHaveValue('');

    // 서버는 원문/부분값 대신 configured만 준다.
    const settingsResponse = await page.request.get('/api/settings');
    expect(settingsResponse.status()).toBe(200);
    const body = await settingsResponse.text();
    expect(body).not.toContain(FAKE_KEY);
    expect(body).not.toContain('****');
    const settingsBody = JSON.parse(body).settings as Record<string, unknown>;
    // 마스킹된 문자열 맵 대신 불리언 상태만 온다.
    expect(settingsBody.api_keys).toBeUndefined();
    const configuredStatus = settingsBody.api_keys_configured as Record<string, unknown>;
    expect(configuredStatus.OPENAI_API_KEY).toBe(true);
    expect(Object.values(configuredStatus).every(value => typeof value === 'boolean')).toBe(true);

    // 2) 재로드해도 입력란은 비어 있고 상태는 서버에서 온다.
    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByRole('heading', { name: '시스템 설정' })).toBeVisible({ timeout: 15_000 });
    await expect(input).toHaveValue('');
    await expect(page.getByTestId('api-key-delete-OPENAI_API_KEY')).toBeVisible();
    expect(await collectPersistedText(page)).not.toContain(FAKE_KEY);

    // 3) 페이지를 떠났다 돌아와도 입력값이 남지 않는다.
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await gotoSettings(page);
    await expect(page.getByTestId('api-key-input-OPENAI_API_KEY')).toHaveValue('');
    expect(await collectPersistedText(page)).not.toContain(FAKE_KEY);

    // 명시적 삭제는 서버 상태를 실제로 바꾼다.
    await page.getByTestId('api-key-delete-OPENAI_API_KEY').click();
    await page.getByRole('button', { name: /설정 저장/ }).click();
    await expect(page.getByText(/저장 완료/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('api-key-delete-OPENAI_API_KEY')).toHaveCount(0);
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('legacy browser-stored API key is purged on load while preferences survive', async ({ browser }) => {
  test.setTimeout(90_000);
  const server = await startSettingsServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  await page.addInitScript((secret: string) => {
    window.localStorage.setItem(
      'agk_user_settings',
      JSON.stringify({
        OPENAI_API_KEY: secret,
        default_model: 'e2e-legacy-model',
        search_engine: 'duckduckgo',
      }),
    );
    window.localStorage.setItem(
      'agk_user_settings:v1',
      JSON.stringify({ GEMINI_API_KEY: secret }),
    );
  }, LEGACY_SECRET);
  try {
    await gotoSettings(page);

    // legacy 저장소 자체가 정리된다.
    expect(await page.evaluate(() => window.localStorage.getItem('agk_user_settings'))).toBeNull();
    expect(await collectPersistedText(page)).not.toContain(LEGACY_SECRET);

    // 브라우저가 소유한 비밀 아닌 preference는 살아남는다(검색 엔진).
    await expect(page.locator('input[name="search_engine"][value="duckduckgo"]')).toBeChecked();
    // CR-06: 기본 모델은 서버 관리 값이므로 브라우저의 오래된 값이 덮어쓰지 않는다.
    const settings = (await (await page.request.get('/api/settings')).json()) as {
      settings: { model?: { name?: string } };
    };
    await expect(page.getByTestId('settings-default-model')).toHaveValue(
      settings.settings.model?.name ?? '',
    );
    // legacy에 있던 키가 폼으로 재주입되지 않는다.
    await expect(page.getByTestId('api-key-input-GEMINI_API_KEY')).toHaveValue('');
  } finally {
    await context.close();
    await server.cleanup();
  }
});
