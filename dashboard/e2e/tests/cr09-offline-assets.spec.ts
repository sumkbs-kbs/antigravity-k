/**
 * CR-09 · 오프라인 로컬 표시 자산 (실제 production 빌드 브라우저)
 * ==============================================================
 * 발견 F05: `dashboard/index.html`이 Google Fonts CSS, highlight.js CDN CSS,
 * mermaid CDN script, diff2html CDN CSS를 head에서 불러왔다. 오프라인/차단
 * 환경에서는 폰트·코드 하이라이트·다이어그램이 깨졌고, mermaid는 초기 로드에
 * 큰 동기 script를 붙였다.
 *
 * 이 스펙은 hermetic 백엔드 + **cold cache** 컨텍스트에서 앱 원점(127.0.0.1)만
 * 허용하고 나머지 네트워크를 차단한 채로:
 *   C09-01 필수 CDN 요청 0
 *   C09-02 cold cache 로컬 표시(Chat/Markdown/코드/Mermaid)
 *   C09-03 sanitize/악성 diagram 회귀 (securityLevel strict 유지)
 *   C09-05 브라우저 network/console 증거(요약을 [C09-EVIDENCE] 한 줄로 남긴다)
 * 를 확인한다. 실제 cloud 추론의 offline 지원은 주장하지 않는다 — 채팅 응답은
 * 이 테스트가 로컬에서 stub한다.
 */
import { test, expect, type Page } from '@playwright/test';

import { DashboardPage } from '../pages/DashboardPage';
import { startNoAuthServer, type HermeticServer } from '../helpers/hermeticBackend';

process.env.AGK_SEC_DEV_NO_PIN_ALLOW = '1';

const CODE_BLOCK = ['```typescript', 'const answer: number = 42;', '```'].join('\n');
const DIAGRAM = ['```mermaid', 'graph TD;', '  A[오프라인 시작] --> B[로컬 렌더];', '```'].join('\n');
const TABLE = ['| 항목 | 값 |', '| --- | --- |', '| 폰트 | 시스템 스택 |'].join('\n');
const MARKDOWN = ['# 오프라인 렌더', TABLE, CODE_BLOCK, DIAGRAM].join('\n\n');
const MALICIOUS_MARKDOWN = [
  ['```mermaid', 'graph TD;', '  A["<img src=x onerror=window.__agkXss=1>"] --> B;', '```'].join('\n'),
].join('\n\n');

const MERMAID_SVG = '.mermaid-container svg';
const CODE_BLOCK_SELECTOR = '.code-block';

/** 승인 큐(action diff) 픽스처 — Monaco DiffEditor가 mount되는 경로다. */
const AGENT_TASKS = {
  status: 'ok',
  data: [
    {
      task_id: 'task-ui',
      prompt: 'probe',
      status: 'running',
      error: null,
      created_at: '2026-08-20T09:00:00Z',
      updated_at: '2026-08-20T09:00:05Z',
    },
  ],
};

const PENDING_APPROVAL = {
  request_id: 'approval-ui',
  tool_name: 'apply_patch',
  risk_level: 'high',
  description: '설정 파일 수정',
  diff_preview: '--- a/settings.ts\n+++ b/settings.ts\n@@ -1 +1 @@\n-old\n+new',
  status: 'pending',
  created_at: 1_777_000_000,
  timeout_sec: 120,
  auto_review: null,
};

interface BrowserEvidence {
  readonly blockedExternal: string[];
  readonly consoleMessages: string[];
  readonly failedResponses: string[];
  readonly fontFaces: FontEvidence;
  readonly highlightApplied: boolean | null;
}

interface FontEvidence {
  /** 로드된 @font-face 패밀리(예: Monaco의 로컬 codicon). */
  readonly families: string[];
  /** 다른 원점에서 가져오는 @font-face src — 반드시 비어 있어야 한다. */
  readonly externalSources: string[];
}

/** CR-09 이전에 head에서 불러오던 웹폰트들 — @font-face로 되살아나면 실패다. */
const REMOVED_WEBFONT_FAMILIES = ['Inter', 'Newsreader', 'JetBrains Mono', 'Instrument Serif'];

/**
 * 오프라인 자산 결함의 지문 — 번들 chunk/스타일/폰트를 외부에서 받다 실패한 흔적.
 * 이 스펙은 이것만 실패로 본다. hermetic 백엔드의 503(auth 미구성) 같은 앱 원점
 * 응답은 CR-09 판정 대상이 아니므로 증거로만 남긴다.
 */
const OFFLINE_FAILURE_PATTERN =
  /(net::ERR|Failed to fetch|Failed to load module|dynamically imported module|Loading chunk|ERR_NAME_NOT_RESOLVED|fonts\.googleapis|cdn\.jsdelivr|unpkg|cdnjs)/i;

/**
 * 앱 원점(로컬 백엔드) 외의 모든 HTTP 요청을 차단하고 기록한다.
 * cold cache 확인을 위해 호출자는 새 browser context를 쓴다.
 */
async function blockExternalTraffic(page: Page, origin: string): Promise<string[]> {
  const blocked: string[] = [];
  await page.route('**/*', route => {
    const url = route.request().url();
    if (url.startsWith(origin)) return route.continue();
    blocked.push(url);
    return route.abort();
  });
  return blocked;
}

function captureBrowserSignals(page: Page, origin: string): { consoleMessages: string[]; failedResponses: string[] } {
  const consoleMessages: string[] = [];
  const failedResponses: string[] = [];
  page.on('console', message => {
    if (message.type() === 'error' || message.type() === 'warning') {
      consoleMessages.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on('pageerror', error => consoleMessages.push(`pageerror: ${error.message}`));
  page.on('requestfailed', request => {
    consoleMessages.push(`requestfailed: ${request.url()} (${request.failure()?.errorText ?? 'unknown'})`);
  });
  page.on('response', response => {
    if (response.status() >= 400 && response.url().startsWith(origin)) {
      failedResponses.push(`${response.status()} ${response.url().replace(origin, '')}`);
    }
  });
  return { consoleMessages, failedResponses };
}

/** `/agent` 실행 추적 화면의 API를 hermetic 픽스처로 고정한다(Monaco diff 진입 경로). */
async function installAgentFixtures(page: Page): Promise<void> {
  await page.addInitScript(() => sessionStorage.setItem('ag_access_token', 'e2e-token'));
  await page.route(/\/api\/session\/info(?:\?.*)?$/, route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, session: { subject: 'e2e' } }),
    }),
  );
  await page.route(/\/api\/tasks(?:\?.*)?$/, route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(AGENT_TASKS) }),
  );
  await page.route(/\/api\/tasks\/task-ui\/events(?:\?.*)?$/, route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ task_id: 'task-ui', events: [], last_sequence: 0, has_more: false }),
    }),
  );
  await page.route(/\/api\/tasks\/task-ui\/events\/stream(?:\?.*)?$/, route =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: stream.end\ndata: {"task_id":"task-ui","last_sequence":0,"status":"done"}\n\n',
    }),
  );
  await page.route(/\/api\/approval\/pending(?:\?.*)?$/, route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ pending: [PENDING_APPROVAL], count: 1 }),
    }),
  );
  await page.route(/\/api\/system\/metrics(?:\?.*)?$/, route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, memory_mb: 512, cpu_percent: 8, total_tokens: 2048 }),
    }),
  );
}

/** 채팅 응답을 로컬에서 고정한다 — 외부 추론 없이 표시 자산만 검증하기 위해서다. */
async function stubAssistantMarkdown(page: Page, markdown: string): Promise<void> {
  await page.route(/\/v1\/chat\/completions$/, route =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        `data: ${JSON.stringify({ choices: [{ delta: { content: markdown } }] })}`,
        'data: [DONE]',
        '',
      ].join('\n\n'),
    }),
  );
}

async function fontFaces(page: Page): Promise<FontEvidence> {
  return page.evaluate(removedFamilies => {
    const faces = Array.from(document.fonts).map(face => face.family.replace(/["']/g, ''));
    const families = [...new Set(faces)].filter(family => removedFamilies.includes(family));
    const externalSources = Array.from(document.styleSheets)
      .flatMap(sheet => {
        try {
          return Array.from(sheet.cssRules);
        } catch {
          return [];
        }
      })
      .filter((rule): rule is CSSFontFaceRule => rule instanceof CSSFontFaceRule)
      .map(rule => rule.style.getPropertyValue('src'))
      .filter(src => /https?:\/\//.test(src) && !src.includes(window.location.origin));
    return { families, externalSources };
  }, REMOVED_WEBFONT_FAMILIES);
}

async function mermaidRendered(page: Page): Promise<boolean> {
  return page.evaluate(() => document.querySelectorAll('svg').length > 0);
}

async function highlightColorsApplied(page: Page): Promise<boolean | null> {
  return page.evaluate(() => {
    const code = document.querySelector('.code-block pre code');
    const token = document.querySelector('.code-block pre code .hljs-keyword');
    if (!(code instanceof HTMLElement) || !(token instanceof HTMLElement)) return null;
    // 로컬로 번들된 테마가 실제로 칠해졌는지: 토큰 색이 기저 코드 색과 달라야 한다.
    return getComputedStyle(token).color !== getComputedStyle(code).color;
  });
}

function logEvidence(evidence: BrowserEvidence): void {
  // C09-05: 실행 로그에 판정 근거를 JSON 한 줄로 남긴다(증거팩 logs에 그대로 보존).
  console.log(`[C09-EVIDENCE] ${JSON.stringify(evidence)}`);
}

test('C09-01/02 · cold cache + 외부 차단에서 Chat/Markdown/코드/Mermaid가 로컬 자산으로 렌더된다', async ({ browser }) => {
  test.setTimeout(120_000);
  const server: HermeticServer = await startNoAuthServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const blocked = await blockExternalTraffic(page, server.baseUrl);
  const { consoleMessages, failedResponses } = captureBrowserSignals(page, server.baseUrl);
  try {
    await stubAssistantMarkdown(page, MARKDOWN);
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.goToChat();
    await dashboard.sendChatMessageViaTextarea('오프라인 표시 자산 확인');
    await expect(page.locator('.message.assistant').first()).toBeVisible({ timeout: 20_000 });

    // Markdown 표 + 코드 블록은 로컬 번들만으로 렌더된다.
    await expect(page.locator(CODE_BLOCK_SELECTOR).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('table').first()).toBeVisible({ timeout: 20_000 });

    // Mermaid는 다이어그램이 보일 때만 지연 로드되어 로컬 chunk로 렌더된다.
    await expect(page.locator(MERMAID_SVG).first()).toBeVisible({ timeout: 30_000 });
    expect(await mermaidRendered(page)).toBe(true);

    const highlightApplied = await highlightColorsApplied(page);
    expect(highlightApplied).toBe(true);

    const fontEvidence = await fontFaces(page);
    // CDN 웹폰트가 @font-face로 남아 있지 않고, 외부 원점 폰트 소스도 없다.
    expect(fontEvidence.families).toEqual([]);
    expect(fontEvidence.externalSources).toEqual([]);

    // C09-01: 외부로 나간 필수 요청이 하나도 없어야 한다.
    expect(blocked).toEqual([]);
    expect(consoleMessages.filter(entry => OFFLINE_FAILURE_PATTERN.test(entry))).toEqual([]);

    logEvidence({ blockedExternal: blocked, consoleMessages, failedResponses, fontFaces: fontEvidence, highlightApplied });
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('C09-01 · 설정 화면도 외부 요청 없이 cold cache에서 로드된다', async ({ browser }) => {
  test.setTimeout(90_000);
  const server: HermeticServer = await startNoAuthServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const blocked = await blockExternalTraffic(page, server.baseUrl);
  const { consoleMessages, failedResponses } = captureBrowserSignals(page, server.baseUrl);
  try {
    await page.goto('/settings');
    await expect(page.getByTestId('settings-default-model')).toBeVisible({ timeout: 30_000 });

    const fontEvidence = await fontFaces(page);
    expect(fontEvidence.families).toEqual([]);
    expect(fontEvidence.externalSources).toEqual([]);
    expect(blocked).toEqual([]);

    logEvidence({ blockedExternal: blocked, consoleMessages, failedResponses, fontFaces: fontEvidence, highlightApplied: null });
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('C09-01/02 · 승인 큐 Monaco diff도 외부 요청 없이 로컬 번들/워커로 렌더된다', async ({ browser }) => {
  test.setTimeout(180_000);
  const server: HermeticServer = await startNoAuthServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const blocked = await blockExternalTraffic(page, server.baseUrl);
  const { consoleMessages, failedResponses } = captureBrowserSignals(page, server.baseUrl);
  try {
    await installAgentFixtures(page);

    await page.goto('/agent');
    // Monaco는 승인 큐가 실제로 그려질 때 mount된다 — 이전에는 이 시점에
    // jsDelivr에서 로더 스크립트와 vs 트리를 받아 왔다(오프라인이면 편집기 없음).
    await expect(page.locator('.monaco-editor:visible').first()).toBeVisible({ timeout: 30_000 });

    expect(blocked).toEqual([]);
    expect(consoleMessages.filter(entry => OFFLINE_FAILURE_PATTERN.test(entry))).toEqual([]);

    logEvidence({
      blockedExternal: blocked,
      consoleMessages,
      failedResponses,
      fontFaces: { families: [], externalSources: [] },
      highlightApplied: null,
    });
  } finally {
    await context.close();
    await server.cleanup();
  }
});

test('C09-03 · 악성 다이어그램 라벨이 실행되지 않고 주입되지도 않는다', async ({ browser }) => {
  test.setTimeout(120_000);
  const server: HermeticServer = await startNoAuthServer();
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const blocked = await blockExternalTraffic(page, server.baseUrl);
  const { consoleMessages, failedResponses } = captureBrowserSignals(page, server.baseUrl);
  try {
    await stubAssistantMarkdown(page, MALICIOUS_MARKDOWN);
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.goToChat();
    await dashboard.sendChatMessageViaTextarea('악성 다이어그램 라벨');
    await expect(page.locator('.message.assistant').first()).toBeVisible({ timeout: 20_000 });

    // 렌더되든 오류로 떨어지든 컨테이너는 존재한다 — 어느 쪽이든 실행/주입은 없어야 한다.
    await expect(page.locator('.mermaid-container').first()).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(2_000);

    const injected = await page.evaluate(() => ({
      xssFlag: (globalThis as unknown as { __agkXss?: number }).__agkXss,
      injectedNodes: document.querySelectorAll('.mermaid-container img, .mermaid-container script').length,
    }));
    expect(await injected.xssFlag).toBeUndefined();
    expect(await injected.injectedNodes).toBe(0);

    expect(blocked).toEqual([]);
    logEvidence({
      blockedExternal: blocked,
      consoleMessages,
      failedResponses,
      fontFaces: { families: [], externalSources: [] },
      highlightApplied: null,
    });
  } finally {
    await context.close();
    await server.cleanup();
  }
});
