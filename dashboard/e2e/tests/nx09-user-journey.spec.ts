/**
 * NX-09 witness — 인증 후 **실제 사용자 동선**을 실 브라우저·실 서버로 잰다.
 *
 * 이 파일이 재는 것 (카드 `docs/18` §NX-09 / `docs/19` §NX-09)
 * ----------------------------------------------------------
 *   T1 인증 후 핵심 동선: PIN UI 로그인 → 모델 선택(UI) → 대화 → 응답
 *   T2 저장 → 재시작 → 이어가기: 서버가 진실이고, **빈 localStorage** 로 새로 연 창이 그 진실을 복원한다
 *   T3 삭제: 서버에서 지운 대화는 조회·export·새 창에서 다시 나타나지 않는다
 *   T4 첨부: 첨부가 모델에게 **도달하는가**(텍스트 주석 vs 이미지 입력)
 *   T5 PIN 변경: 저장 토큰 제거 + 재로그인 모달 (NX-05 의 UI 배선 — HEAD dist 에는 없다)
 *   T6 새 대화 정체성: 첫 대화가 서버 폴백 id(`conv_unspecified`)로 합쳐지지 않는다
 *   T7 PIN 변경 → 열린 이벤트 WS 폐기(같은 창, HTTP API 경로) — 서버 로그와 소켓을 함께 본다
 *   T8 PIN 변경 → **다른 창**의 살아 있는 이벤트 WS 폐기(실 UI 설정 화면 경로, 카드 계약 ≤5초)
 *
 * 무엇으로 재는가
 * ---------------
 * - **실 hermetic 서버**(`startAuthServer`): 실제 PIN 해시·실제 JWT·실제 대화 저장소.
 * - **가짜 provider**(`startFakeProvider`): 브라우저 page.route 로 가로채면 **서버→provider** 구간이
 *   사라진다(그러면 "화면이 SSE 를 그리는가"만 재게 된다). 여기서는 제품 서버가 실제로 HTTP 를 친다.
 * - **화면이 실제로 보낸 것**: provider 가 받은 본문과 브라우저 요청을 함께 기록한다.
 *
 * 표시: 이 증거는 **fake provider** 결과다 — cloud/live provider 지원의 증거가 아니다(NX-09 품질 분리).
 *
 * 소유: `dashboard-e2e-witnesses` 게이트는 `cr\d+-` 이름 규칙을 소유한다(NX-09 는 그 목록 밖).
 */

import { mkdtemp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { expect, test, type BrowserContext, type Page } from '@playwright/test';

import { startFakeProvider, type FakeProvider } from '../helpers/fakeProvider';
import { authPin, startAuthServer, type HermeticServer } from '../helpers/hermeticBackend';

/** 가짜 provider 만 보내는 표식 — 이 문자열이 화면에 있으면 요청이 **그** provider 까지 갔다. */
const FAKE_REPLY_MARKER = 'NX09-FAKE-PROVIDER-응답';
const FAKE_MODEL_ID = 'fake-model-a';
const ARTIFACT_DIR = process.env.NX09_ARTIFACT_DIR
  ?? path.resolve(process.cwd(), '..', 'docs', 'qa', '2026-09-16-followup', 'nx09');
const NEW_PIN = 'e2e-nx09-new-pin';

/**
 * 서빙되는 SPA 가 **현재 소스**인지 먼저 확인한다(NX-09-F04).
 *
 * 커밋된 `dashboard_dist` 는 소스보다 낡을 수 있고, 그러면 이 증인은 **다른 제품**을 재면서 원인을
 * 알 수 없는 실패를 낸다. 그 경우 `pnpm build` 를 하라고 **명시적으로** 실패한다.
 */
async function assertServedBundleMatchesSources(): Promise<void> {
  const assetsDir = path.resolve(process.cwd(), '..', 'src', 'antigravity_k', 'dashboard_dist', 'assets');
  // 표식은 서로 다른 청크에 있을 수 있다(PinModal 청크 / ChatPage 청크) — 파일별로 찾는다.
  let noticeMarker = false;
  let fallbackMarker = false;
  let attachmentMarker = false;
  try {
    const entries = await readdir(assetsDir);
    for (const entry of entries) {
      if (!entry.endsWith('.js')) continue;
      const text = await readFile(path.join(assetsDir, entry), 'utf8');
      if (text.includes('pin-modal-notice')) noticeMarker = true;
      if (text.includes('conv_unspecified')) fallbackMarker = true;
      // NX-09-F03: 첨부가 실제로 전송되는 UI 표식 — 없으면 낡은 번들을 재게 된다.
      if (text.includes('chat-attachment-chip')) attachmentMarker = true;
    }
  } catch {
    noticeMarker = false;
    fallbackMarker = false;
    attachmentMarker = false;
  }
  expect(
    noticeMarker && fallbackMarker && attachmentMarker,
    'NX-09-F04: 커밋된 dashboard_dist 가 소스보다 낡았다 — `cd dashboard && pnpm build` 후 다시 실행하라',
  ).toBe(true);
}

interface Journey {
  readonly provider: FakeProvider;
  readonly server: HermeticServer;
  readonly projectPath: string;
  readonly cleanup: () => Promise<void>;
}

async function startJourney(): Promise<Journey> {
  await assertServedBundleMatchesSources();
  const provider = await startFakeProvider({ defaultText: FAKE_REPLY_MARKER });
  const stateDirectory = await mkdtemp(path.join(tmpdir(), 'agk-nx09-'));
  await mkdir(path.join(stateDirectory, 'data'), { recursive: true });
  await writeFile(
    path.join(stateDirectory, 'data', 'projects.json'),
    JSON.stringify([
      {
        id: 'default',
        name: 'nx09-journey',
        path: stateDirectory,
        is_active: true,
        last_accessed_at: '2026-01-05T09:00:00.000000',
        tasks: [],
      },
    ], null, 2),
    { encoding: 'utf8' },
  );
  const server = await startAuthServer(1, {
    stateDirectory,
    workingDirectory: stateDirectory,
    overrides: {
      AGK_TASK_DB_PATH: path.join(stateDirectory, 'tasks.db'),
      AGK_ALLOWED_ROOTS: stateDirectory,
      // 대화 저장소를 격리한다 — 격리하지 않으면 이 시험은 **개발 기계의 홈**을 읽고
      // CR-01 migration gate(503)에 걸린다(실측: legacy_record_count=3).
      AGK_CONVERSATION_STORE_DIR: path.join(stateDirectory, 'conversations'),
      // 로컬 모델 발견이 실 기계의 ollama(11434)가 아니라 **가짜 provider** 를 보게 한다.
      AGK_OLLAMA_API_BASE: provider.origin,
      AGK_MODEL_API_ENGINE: 'ollama',
      AGK_MODEL_API_BASE: provider.apiBase,
      AGK_MODEL_API_KEY: 'fake',
      AGK_PROVIDER: 'ollama',
    },
  });
  return {
    provider,
    server,
    projectPath: stateDirectory,
    cleanup: async () => {
      await server.cleanup();
      await provider.stop();
      await rm(stateDirectory, { recursive: true, force: true });
    },
  };
}

async function loginThroughUi(page: Page): Promise<void> {
  await page.goto('/');
  const dialog = page.locator('[role="dialog"][aria-label="PIN 인증"]');
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.locator('input').first().fill(authPin);
  await dialog.getByRole('button', { name: /잠금 해제|확인/ }).first().click();
  await expect(dialog).toHaveCount(0, { timeout: 20_000 });
}

/** 모델을 **UI 로** 고른다(가짜 provider 의 모델). */
async function pickFakeModel(page: Page): Promise<void> {
  await page.locator('button[aria-label="모델 선택"]').first().click();
  const row = page.locator('.model-choice-row').filter({ hasText: FAKE_MODEL_ID }).first();
  await row.waitFor({ state: 'visible', timeout: 20_000 });
  await row.click();
  await expect(page.locator('.model-select-trigger .model-name-text').first()).toContainText(FAKE_MODEL_ID);
}

async function sendAndAwaitReply(page: Page, text: string, marker: string = FAKE_REPLY_MARKER): Promise<void> {
  const before = await page.locator('.message.assistant .bubble').filter({ hasText: marker }).count();
  await page.locator('textarea#chat-input').fill(text);
  await page.locator('.send-btn').first().click();
  // 두 번째 턴에서는 첫 응답이 이미 화면에 있으므로 "개수 증가"로 기다린다.
  await expect
    .poll(async () => page.locator('.message.assistant .bubble').filter({ hasText: marker }).count(), {
      timeout: 120_000,
      intervals: [500],
    })
    .toBeGreaterThan(before);
}

async function bearer(page: Page): Promise<string> {
  const token = await page.evaluate(() => sessionStorage.getItem('ag_access_token'));
  if (!token) throw new Error('화면이 bearer 를 갖고 있지 않다');
  return token;
}

/**
 * 화면이 들고 있는 활성 대화 id(= activeSessionId). 서버 계약의 conversation_id 와 같다.
 *
 * 키는 `antigravity_chat_` + **activeProjectId**(없으면 경로)이다 — 경로만 가정하면 이 증인은
 * 자기 전제를 틀리게 잡고 "화면이 저장하지 않았다"로 거짓 실패한다(첫 판본이 그렇게 실패했다).
 */
async function conversationIdOf(page: Page, projectPath: string): Promise<string> {
  const candidates = [`antigravity_chat_default`, `antigravity_chat_${projectPath}`];
  for (const key of candidates) {
    const raw = await page.evaluate((k) => window.localStorage.getItem(k), key);
    if (!raw) continue;
    const parsed = JSON.parse(raw) as { activeSessionId?: string };
    if (parsed.activeSessionId) return parsed.activeSessionId;
  }
  throw new Error('화면이 대화 상태를 저장하지 않았다');
}

/**
 * provider 본문은 JSON 이스케이프된 유니코드(`\uXXXX`)를 쓴다 — 원문 includes 는 **거짓 실패**를
 * 만든다(첫 판본이 정확히 그렇게 실패했다: 화면에는 답이 보이는데 provider 본문 비교는 false).
 * 비교 전에 이스케이프를 풀어 **같은 문자열**로 만든다.
 */
function jsonUnescape(body: string): string {
  return body.replace(/\\u([0-9a-fA-F]{4})/g, (_match, hex: string) =>
    String.fromCharCode(Number.parseInt(hex, 16)),
  );
}

function bodyContainsPrompt(body: string, prompt: string): boolean {
  return body.includes(prompt) || jsonUnescape(body).includes(prompt);
}

/** 대화 저장소 파일 목록(중첩 디렉터리 포함). */
async function readdirRecursive(root: string): Promise<string[]> {
  const found: string[] = [];
  const walk = async (directory: string): Promise<void> => {
    let entries: Awaited<ReturnType<typeof readdir>>;
    try {
      entries = await readdir(directory);
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(directory, entry);
      if (entry.startsWith('.')) continue;
      try {
        const info = await readdir(full);
        void info;
        await walk(full);
      } catch {
        found.push(full);
      }
    }
  };
  await walk(root);
  return found;
}

/** 새 브라우저 창(빈 localStorage) + **대화 id 만** 심는다 — 이력은 서버에서 와야 한다. */
async function freshContextSeededWith(
  context: BrowserContext,
  projectPath: string,
  conversationId: string,
): Promise<Page> {
  const page = await context.newPage();
  await page.addInitScript(({ keys, payload, projectKey, projectPath: project }) => {
    window.localStorage.setItem(projectKey, project);
    for (const key of keys) window.localStorage.setItem(key, JSON.stringify(payload));
  }, {
    keys: [`antigravity_chat_default`, `antigravity_chat_${projectPath}`],
    payload: {
      activeSessionId: conversationId,
      sessions: [{
        id: conversationId,
        title: 'restored',
        updatedAt: new Date().toISOString(),
        messages: [],
        conversationRevision: 0,
      }],
    },
    projectKey: 'agk_active_project',
    projectPath,
  });
  return page;
}

function writeArtifact(name: string, payload: unknown): Promise<void> {
  return (async () => {
    await mkdir(ARTIFACT_DIR, { recursive: true });
    await writeFile(path.join(ARTIFACT_DIR, name), JSON.stringify(payload, null, 2), { encoding: 'utf8' });
  })();
}

test.describe('NX-09 인증 후 실제 사용자 동선', () => {
  test('T1 PIN UI 로그인 → 모델 선택 → 대화 → 가짜 provider 응답이 화면과 provider 에 함께 있다', async ({ browser }) => {
    test.setTimeout(240_000);
    const journey = await startJourney();
    const context = await browser.newContext({ baseURL: journey.server.baseUrl, viewport: { width: 1280, height: 800 } });
    try {
      const page = await context.newPage();
      const asked = 'NX-09 T1 사용자 요청';
      await loginThroughUi(page);
      await page.goto('/chat');
      await pickFakeModel(page);
      await sendAndAwaitReply(page, asked);

      const assistant = await page.locator('.message.assistant .bubble').first().innerText();
      const providerBodies = journey.provider.hits.map((hit) => hit.body);
      const reachedProvider = providerBodies.some((body) => bodyContainsPrompt(body, asked));

      await context.storageState({ path: path.join(ARTIFACT_DIR, 't1-storage.json') }).catch(() => undefined);
      await writeArtifact('t1-observation.json', {
        asked,
        assistantText: assistant.slice(0, 400),
        providerPaths: journey.provider.hits.map((hit) => hit.path),
        reachedProvider,
      });

      expect(assistant, '가짜 provider 의 표식이 화면에 있어야 한다').toContain(FAKE_REPLY_MARKER);
      expect(reachedProvider, '사용자 요청이 실제로 provider 까지 가야 한다').toBe(true);
    } finally {
      await context.close();
      await journey.cleanup();
    }
  });

  test('T2 서버가 진실이다 — 빈 localStorage 로 새로 연 창이 저장된 이력을 복원한다', async ({ browser }) => {
    test.setTimeout(240_000);
    const journey = await startJourney();
    const first = await browser.newContext({ baseURL: journey.server.baseUrl });
    try {
      const page = await first.newPage();
      const asked = 'NX-09 T2 영속성 요청';
      await loginThroughUi(page);
      await page.goto('/chat');
      await pickFakeModel(page);
      await sendAndAwaitReply(page, asked);

      const conversationId = await conversationIdOf(page, journey.projectPath);
      const token = await bearer(page);
      const snapshot = await page.request.get(
        `${journey.server.baseUrl}/v1/conversations/${encodeURIComponent(conversationId)}?project_id=default`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const snapshotBody = (await snapshot.json()) as {
        snapshot?: { revision?: number; message_count?: number };
        messages?: Array<{ role: string; content: string }>;
      };

      const second = await browser.newContext({ baseURL: journey.server.baseUrl });
      const historyCalls: string[] = [];
      let restoredVisible = false;
      let freshBodyText = '';
      try {
        const fresh = await freshContextSeededWith(second, journey.projectPath, conversationId);
        fresh.on('request', (request) => {
          if (request.url().includes('/v1/conversations')) historyCalls.push(`→ ${request.method()} ${request.url()}`);
        });
        fresh.on('response', (response) => {
          if (response.url().includes('/v1/conversations')) {
            historyCalls.push(`← ${response.status()} ${response.url()}`);
          }
        });
        await loginThroughUi(fresh);
        await fresh.goto('/chat');
        const restored = fresh.locator('.message.user .bubble').filter({ hasText: asked });
        try {
          await expect(restored.first(), '서버 진실로 이력이 복원되어야 한다').toBeVisible({ timeout: 60_000 });
          restoredVisible = true;
        } catch {
          restoredVisible = false;
        }
        freshBodyText = (await fresh.locator('body').innerText()).slice(0, 1_200);
        await writeArtifact('t2-observation.json', {
          conversationId,
          snapshotStatus: snapshot.status(),
          snapshot: snapshotBody.snapshot,
          messageRoles: (snapshotBody.messages ?? []).map((m) => m.role),
          restoredFromServer: restoredVisible,
          historyCalls,
          freshBodyText,
        });
        expect(restoredVisible, '서버 진실로 이력이 복원되어야 한다').toBe(true);
      } finally {
        await second.close();
      }

      expect(snapshot.status(), '서버가 대화를 알고 있어야 한다').toBe(200);
      expect(snapshotBody.snapshot?.revision ?? 0, '저장된 대화는 리비전이 올라가 있어야 한다').toBeGreaterThan(0);
      expect(
        (snapshotBody.messages ?? []).some((m) => m.role === 'user' && m.content.includes(asked)),
        '서버 원본에 사용자 턴이 있어야 한다',
      ).toBe(true);
    } finally {
      await first.close();
      await journey.cleanup();
    }
  });

  test('T3 삭제한 대화는 조회·export·새 창에서 다시 나타나지 않는다', async ({ browser }) => {
    test.setTimeout(240_000);
    const journey = await startJourney();
    const context = await browser.newContext({ baseURL: journey.server.baseUrl });
    try {
      const page = await context.newPage();
      const asked = 'NX-09 T3 삭제 대상';
      await loginThroughUi(page);
      await page.goto('/chat');
      await pickFakeModel(page);
      await sendAndAwaitReply(page, asked);

      const conversationId = await conversationIdOf(page, journey.projectPath);
      const token = await bearer(page);
      const headers = { Authorization: `Bearer ${token}` };
      const base = journey.server.baseUrl;
      const deleted = await page.request.delete(
        `${base}/v1/conversations/${encodeURIComponent(conversationId)}?project_id=default`,
        { headers },
      );
      const afterSnapshot = await page.request.get(
        `${base}/v1/conversations/${encodeURIComponent(conversationId)}?project_id=default`,
        { headers, failOnStatusCode: false },
      );
      const afterExport = await page.request.get(
        `${base}/v1/conversations/${encodeURIComponent(conversationId)}/export?project_id=default`,
        { headers, failOnStatusCode: false },
      );
      const afterHistory = await page.request.get(
        `${base}/v1/conversations/${encodeURIComponent(conversationId)}/history?project_id=default`,
        { headers, failOnStatusCode: false },
      );

      const second = await browser.newContext({ baseURL: base });
      let seenInFreshWindow = false;
      try {
        const fresh = await freshContextSeededWith(second, journey.projectPath, conversationId);
        await loginThroughUi(fresh);
        await fresh.goto('/chat');
        await fresh.waitForTimeout(6_000);
        seenInFreshWindow = (await fresh.locator('.message.user .bubble').filter({ hasText: asked }).count()) > 0;
      } finally {
        await second.close();
      }

      await writeArtifact('t3-observation.json', {
        conversationId,
        deleteStatus: deleted.status(),
        afterSnapshotStatus: afterSnapshot.status(),
        afterExportStatus: afterExport.status(),
        afterHistoryStatus: afterHistory.status(),
        seenInFreshWindow,
      });

      expect([200, 204]).toContain(deleted.status());
      expect([404, 410]).toContain(afterSnapshot.status());
      expect([404, 410]).toContain(afterExport.status());
      expect([404, 410]).toContain(afterHistory.status());
      expect(seenInFreshWindow, '삭제된 대화의 원문이 새 창에 나타나면 안 된다').toBe(false);
    } finally {
      await context.close();
      await journey.cleanup();
    }
  });

  /**
   * T4 — NX-09-F03 계약(수정 후): 첨부 이미지가 **실제 바이트로** 모델에게 가고, 그 턴에만 간다.
   *
   * 예전의 이 시험은 `test.fail` 로 고정된 결함 증인이었다(첨부가 `[첨부 파일: …]` 텍스트로만
   * 가고 바이트는 어디에도 없었다). 수정으로 계약이 바뀌었으므로 "미리 실패" 장치를 제거하고
   * 실제 계약을 잰다: ① 화면이 첨부를 보여 주고 ② provider 본문에 PNG 의 base64 가 있고
   * ③ **다음 턴에는 다시 실리지 않는다**(ADR-0005: 바이트는 그 턴의 입력으로만 간다).
   */
  test('T4 첨부한 이미지가 실제 바이트로 모델에게 도달한다 (그 턴에만)', async ({ browser }) => {
    test.setTimeout(240_000);
    const journey = await startJourney();
    const context = await browser.newContext({ baseURL: journey.server.baseUrl });
    try {
      const page = await context.newPage();
      await loginThroughUi(page);
      await page.goto('/chat');
      await pickFakeModel(page);

      // 1x1 PNG — 실제 이미지 바이트. 첨부 UI 로 넣는다.
      const png = Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AF+6L4AAAAASUVORK5CYII=',
        'base64',
      );
      const filePath = path.join(journey.projectPath, 'nx09-attach.png');
      await writeFile(filePath, png);
      await page.locator('input[type="file"]').first().setInputFiles(filePath);
      await page.waitForTimeout(1_000);
      const composerText = await page.locator('textarea#chat-input').inputValue();
      const chip = page.locator('[data-testid="chat-attachment-chip"]').first();
      const chipVisible = (await chip.count()) > 0;
      const chipText = chipVisible ? ((await chip.textContent()) ?? '').trim() : '';
      const chipMime = chipVisible ? await chip.getAttribute('data-attachment-mime') : null;

      const chatStatuses: Array<{ status: number; body: string }> = [];
      page.on('response', (response) => {
        if (!response.url().includes('/v1/chat/completions')) return;
        const status = response.status();
        void response
          .text()
          .then((text) => chatStatuses.push({ status, body: text.slice(0, 400) }))
          .catch(() => chatStatuses.push({ status, body: '(본문 없음)' }));
      });

      try {
        await sendAndAwaitReply(page, 'NX-09 T4 첨부 요청');
      } catch (error) {
        // 실패 시 **서버 로그를 함께** 남긴다 — 없으면 원인 추적이 불가능하다.
        await writeArtifact('t4-failure.json', {
          chatStatuses,
          serverLogTail: journey.server.output().split('\n').slice(-60),
          providerPaths: journey.provider.hits.map((hit) => hit.path),
        });
        throw error;
      }

      /** PNG base64 접두사 — 이 문자열이 있으면 **바이트가** 갔다는 뜻이다(표식이 아니라). */
      const pngBase64Prefix = png.toString('base64').slice(0, 16);
      const firstTurnHits = journey.provider.hits.length;
      const firstTurnWithImage = journey.provider.hits
        .slice(0, firstTurnHits)
        .filter((hit) => hit.body.includes(pngBase64Prefix));

      // 두 번째 턴(첨부 없음) — 이력은 서버 저장소가 진실이고 거기엔 base64 가 없다(ADR-0005).
      await sendAndAwaitReply(page, 'NX-09 T4 두 번째 턴');
      const secondTurnHits = journey.provider.hits.slice(firstTurnHits);
      const secondTurnWithImage = secondTurnHits.filter((hit) => hit.body.includes(pngBase64Prefix));

      await writeArtifact('t4-observation.json', {
        composerText,
        chipVisible,
        chipText,
        chipMime,
        imageReachedProvider: firstTurnWithImage.length > 0,
        imageSurfaces: firstTurnWithImage.map((hit) => hit.path),
        firstTurnProviderHits: firstTurnHits,
        secondTurnProviderHits: secondTurnHits.length,
        secondTurnWithImage: secondTurnWithImage.length,
        providerPaths: journey.provider.hits.map((hit) => hit.path),
      });

      expect(composerText, '파일명 표식은 이력 참조로 남아야 한다').toContain('nx09-attach.png');
      expect(chipVisible, '첨부는 전송 전에 화면에 보여야 한다').toBe(true);
      expect(chipMime, '화면이 MIME 을 알아야 서버가 거부할 형식을 미리 걸러낼 수 있다').toBe('image/png');
      expect(firstTurnWithImage.length, '첨부 이미지 바이트가 provider 요청에 실려야 한다').toBeGreaterThan(0);
      expect(secondTurnWithImage.length, '바이트는 그 턴에만 간다(이력으로 재전송되지 않는다)').toBe(0);
    } finally {
      await context.close();
      await journey.cleanup();
    }
  });

  test('T5 PIN 변경은 저장 토큰을 지우고 재로그인 모달을 띄운다 (NX-05 UI 배선)', async ({ browser }) => {
    test.setTimeout(240_000);
    const journey = await startJourney();
    const context = await browser.newContext({ baseURL: journey.server.baseUrl });
    try {
      const page = await context.newPage();
      // 로그인 **전에** 관측기를 붙인다 — 인증 뒤 열리는 이벤트 WS 를 놓치면 폐기를 볼 수 없다.
      const eventSockets: Array<{ url: string; socket: import('@playwright/test').WebSocket; closed: boolean }> = [];
      page.on('websocket', (socket) => {
        if (!socket.url().includes('/ws/events')) return;
        const entry = { url: socket.url(), socket, closed: false };
        socket.on('close', () => { entry.closed = true; });
        eventSockets.push(entry);
      });
      await loginThroughUi(page);
      expect(await page.evaluate(() => sessionStorage.getItem('ag_access_token'))).toBeTruthy();

      const changePinCalls: string[] = [];
      page.on('response', (response) => {
        if (response.url().includes('/api/auth/change-pin')) {
          changePinCalls.push(`← ${response.status()}`);
          void response.text()
            .then((text) => changePinCalls.push(`body ${text.slice(0, 200)}`))
            .catch(() => undefined);
        }
      });

      await page.goto('/settings');
      const currentPin = page.locator('[data-testid="settings-current-pin"]');
      await currentPin.waitFor({ state: 'visible', timeout: 30_000 });
      await currentPin.fill(authPin);
      await page.locator('[data-testid="settings-new-pin"]').fill(NEW_PIN);
      await page.locator('[data-testid="settings-confirm-pin"]').fill(NEW_PIN);
      await page.locator('[data-testid="settings-change-pin"]').click();

      const status = page.locator('[data-testid="settings-pin-status"]');
      let statusText = '';
      try {
        // 모달이 뜨면 상태 메시지는 가려진다 — **존재**를 기다리고 textContent 로 읽는다.
        await status.waitFor({ state: 'attached', timeout: 30_000 });
        statusText = ((await status.textContent()) ?? '').trim();
      } catch {
        statusText = '(상태 메시지 없음)';
      }
      const dialog = page.locator('[role="dialog"][aria-label="PIN 인증"]');
      const dialogVisible = await dialog.isVisible().catch(() => false);
      const tokenAfter = await page.evaluate(() => sessionStorage.getItem('ag_access_token'));
      const notice = page.locator('[data-testid="pin-modal-notice"]');
      const noticeText = (await notice.count()) > 0 ? ((await notice.textContent()) ?? '').trim() : '';

      // 열린 이벤트 WS 가 실제로 끊기었는가(최대 15초 관측).
      let closedSockets = 0;
      for (let tick = 0; tick < 30; tick += 1) {
        closedSockets = eventSockets.filter((entry) => entry.socket.isClosed()).length;
        if (eventSockets.length > 0 && closedSockets === eventSockets.length) break;
        await page.waitForTimeout(500);
      }
      await writeArtifact('t5-observation.json', {
        statusText,
        changePinCalls,
        pinDialogVisible: dialogVisible,
        tokenCleared: !tokenAfter,
        noticeText,
        serverWsLog: journey.server
          .output()
          .split('\n')
          .filter((line) => /ws\/events|Session revoked|WebSocket/.test(line))
          .slice(-20),
        eventSockets: eventSockets.map((entry) => ({
          url: entry.url.replace(/ticket=[^&]+/, 'ticket=<redacted>'),
          isClosed: entry.socket.isClosed(),
          closeEvent: entry.closed,
        })),
        closedSockets,
        bodyText: (await page.locator('body').innerText()).slice(0, 600),
      });

      expect(changePinCalls[0], 'PIN 변경 요청이 실제로 나가야 한다').toBe('← 200');
      expect(dialogVisible, 'PIN 변경 뒤에는 새 PIN 으로 다시 로그인해야 한다').toBe(true);
      // 상태 메시지(설정 화면)는 모달이 앱을 대체하면서 **unmount 된다** — 그래서 사용자에게 남는
      // 유일한 설명은 모달의 notice 다. 설정 화면 문구는 여기서 요구하지 않는다(관측 기록만 남긴다).
      //
      // NX-09 주의: 이 경로의 `sessions_revoked: 0` 은 **정상**이다(폐기할 연결이 없다).
      // `page.goto('/settings')` 가 문서를 통째로 바꾸면서 채팅 화면(=WS 소유자, ChatPage)이
      // unmount 되고 `useEventWebSocket` 의 cleanup 이 소켓을 닫는다 — 즉 요청 시점의 레지스트리가
      // 비어 있다. 여기 남는 `isClosed: false` 는 **계기 오독**이다(파괴된 창의 소켓 객체는 close 를
      // 보고하지 않는다). 폐기 계약은 살아 있는 창을 둔 **T8(다른 창에서 변경)** 이 잰다.
      expect(noticeText, '왜 로그아웃되었는지 모달이 설명해야 한다').toContain('세션');


      expect(tokenAfter, '폐기된 토큰을 남기면 모든 요청이 401 을 반복한다').toBeFalsy();

      // 새 PIN 으로 다시 로그인하면 실제로 열린다(구 PIN 은 은퇴했다).
      await dialog.locator('input').first().fill(NEW_PIN);
      await dialog.getByRole('button', { name: /잠금 해제|확인/ }).first().click();
      await expect(dialog).toHaveCount(0, { timeout: 20_000 });
      expect(await page.evaluate(() => sessionStorage.getItem('ag_access_token'))).toBeTruthy();
    } finally {
      await context.close();
      await journey.cleanup();
    }
  });

  test('T7 PIN 변경은 열린 이벤트 WS 를 닫는다 — 서버 로그와 소켓을 함께 본다', async ({ browser }) => {
    test.setTimeout(240_000);
    const journey = await startJourney();
    const context = await browser.newContext({ baseURL: journey.server.baseUrl });
    try {
      const page = await context.newPage();
      const sockets: Array<{ socket: import('@playwright/test').WebSocket; closed: boolean; url: string }> = [];
      page.on('websocket', (socket) => {
        if (!socket.url().includes('/ws/events')) return;
        const entry = { socket, closed: false, url: socket.url() };
        socket.on('close', () => { entry.closed = true; });
        sockets.push(entry);
      });
      await loginThroughUi(page);
      // 화면이 실제로 이벤트 WS 를 연 뒤에 시작한다.
      for (let tick = 0; tick < 40 && sockets.length === 0; tick += 1) await page.waitForTimeout(250);

      const token = await bearer(page);
      const response = await page.request.post(`${journey.server.baseUrl}/api/auth/change-pin`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { current_pin: authPin, new_pin: NEW_PIN },
      });
      const body = (await response.json()) as { sessions_revoked?: number };

      let closedSockets = 0;
      for (let tick = 0; tick < 60; tick += 1) {
        closedSockets = sockets.filter((entry) => entry.socket.isClosed() || entry.closed).length;
        if (sockets.length > 0 && closedSockets === sockets.length) break;
        await page.waitForTimeout(250);
      }
      const serverDisconnectLog = journey.server
        .output()
        .split('\n')
        .filter((line) => line.includes('ws/events') || line.includes('Could not close'))
        .slice(-10);
      await writeArtifact('t7-observation.json', {
        changePinStatus: response.status(),
        sessionsRevoked: body.sessions_revoked ?? null,
        sockets: sockets.length,
        closedSockets,
        serverDisconnectLog,
      });

      expect(sockets.length, '이벤트 WS 가 열려야 이 계약을 잴 수 있다').toBeGreaterThan(0);
      expect(body.sessions_revoked, '서버는 폐기한 연결 수를 정직하게 보고해야 한다').toBeGreaterThan(0);
      expect(closedSockets, '폐기된 뒤 브라우저 소켓은 닫혀 있어야 한다').toBe(sockets.length);
      expect(serverDisconnectLog.join('\n'), '서버 로그에 이벤트 WS 종료가 남아야 한다')
        .toContain('ws/events');
    } finally {
      await context.close();
      await journey.cleanup();
    }
  });

  /**
   * T8 — NX-09-F06 재검증: **다른 창에서 PIN 을 바꾸면 살아 있는 이벤트 WS 가 닫히는가.**
   *
   * F06 의 원래 관측("설정 화면 경로에서 PIN 을 바꾸면 소켓이 남고 `sessions_revoked: 0`")은
   * **두 창이 아니라 한 창 안에서** 재고 있었다. 그 한 창은 `page.goto('/settings')` 로 문서가
   * 통째로 교체되는 순간 **채팅 화면(WS 소유자)이 사라진다** — 즉 잴 시점에 살아 있는 연결이 없다.
   * 게다가 Playwright 의 소켓 객체는 그 창이 파괴된 뒤에도 `isClosed() === false` 로 남아
   * "소켓이 살아 있다"로 오독된다(계기는 파괴된 창의 close 를 보고하지 않는다).
   *
   * 그래서 이 증인은 **자를 바꿔** 잰다: 창 A 는 채팅 화면에 그대로 두어 WS 를 살려 두고
   * (화면 이동 없음), 창 B 의 설정 화면에서 PIN 을 바꾼다. 창 A 의 소켓 객체는 살아 있는 창의
   * 것이므로 close 를 정직하게 보고한다. 폐기 계약(카드: ≤5초)은 이 경로에서만 주장할 수 있다.
   */
  test('T8 다른 창에서 PIN 을 바꾸면 살아 있는 이벤트 WS 가 5초 안에 닫힌다 (F06 재검증)', async ({ browser }) => {
    test.setTimeout(240_000);
    const journey = await startJourney();
    const context = await browser.newContext({ baseURL: journey.server.baseUrl });
    try {
      // ── 창 A: 채팅 화면. 이 창은 **이동하지 않는다** — 소켓이 살아 있어야 이 계약을 잴 수 있다.
      const chatTab = await context.newPage();
      const chatSockets: Array<{
        socket: import('@playwright/test').WebSocket;
        url: string;
        closeEvent: boolean;
        closedAt: number;
      }> = [];
      chatTab.on('websocket', (socket) => {
        if (!socket.url().includes('/ws/events')) return;
        const entry = { socket, url: socket.url(), closeEvent: false, closedAt: 0 };
        socket.on('close', () => { entry.closeEvent = true; entry.closedAt = Date.now(); });
        chatSockets.push(entry);
      });
      await loginThroughUi(chatTab);
      for (let tick = 0; tick < 60 && chatSockets.length === 0; tick += 1) await chatTab.waitForTimeout(250);
      expect(chatSockets.length, '창 A 가 이벤트 WS 를 열어야 이 계약을 잴 수 있다').toBeGreaterThan(0);
      // 소켓이 **등록될** 시간을 준다(게이트는 accept 직후 등록한다).
      await chatTab.waitForTimeout(1_000);

      // ── 창 B: 설정 화면. 별도 창 = 별도 sessionStorage 이므로 직접 로그인해야 한다.
      const settingsTab = await context.newPage();
      const settingsSockets: string[] = [];
      settingsTab.on('websocket', (socket) => {
        if (socket.url().includes('/ws/events')) settingsSockets.push(socket.url().replace(/ticket=[^&]+/, 'ticket=<redacted>'));
      });
      await loginThroughUi(settingsTab);
      await settingsTab.goto('/settings');
      const currentPin = settingsTab.locator('[data-testid="settings-current-pin"]');
      await currentPin.waitFor({ state: 'visible', timeout: 30_000 });

      const revoked: number[] = [];
      settingsTab.on('response', (response) => {
        if (!response.url().includes('/api/auth/change-pin')) return;
        void response
          .json()
          .then((body) => revoked.push((body as { sessions_revoked?: number }).sessions_revoked ?? -1))
          .catch(() => undefined);
      });

      await currentPin.fill(authPin);
      await settingsTab.locator('[data-testid="settings-new-pin"]').fill(NEW_PIN);
      await settingsTab.locator('[data-testid="settings-confirm-pin"]').fill(NEW_PIN);
      const clickedAt = Date.now();
      await settingsTab.locator('[data-testid="settings-change-pin"]').click();

      // 응답이 오더라도 창 A 의 소켓이 닫히기 전일 수 있다 — 둘 다 기다린 뒤 판정한다.
      await expect
        .poll(() => revoked.length, { timeout: 30_000, intervals: [100] })
        .toBeGreaterThan(0);
      const respondedAt = Date.now();
      for (let tick = 0; tick < 50; tick += 1) {
        if (chatSockets.every((entry) => entry.socket.isClosed() || entry.closeEvent)) break;
        await settingsTab.waitForTimeout(100);
      }

      const closedChatSockets = chatSockets.filter((entry) => entry.socket.isClosed() || entry.closeEvent).length;
      const closeLatencyMs = chatSockets
        .map((entry) => entry.closedAt - clickedAt)
        .filter((value) => value > 0);
      await writeArtifact('t8-observation.json', {
        sessionsRevoked: revoked[0] ?? null,
        chatSockets: chatSockets.map((entry) => ({
          url: entry.url.replace(/ticket=[^&]+/, 'ticket=<redacted>'),
          isClosed: entry.socket.isClosed(),
          closeEvent: entry.closeEvent,
        })),
        closedChatSockets,
        closeLatencyMs,
        observedWithinMs: Date.now() - clickedAt,
        respondedWithinMs: respondedAt - clickedAt,
        settingsTabSockets: settingsSockets,
        chatTabModalVisible: await chatTab
          .locator('[role="dialog"][aria-label="PIN 인증"]')
          .isVisible()
          .catch(() => false),
      });

      expect(revoked[0], '서버는 폐기한 연결 수를 정직하게 보고해야 한다').toBeGreaterThan(0);
      expect(closedChatSockets, '창 A 의 살아 있는 소켓은 닫혀야 한다').toBe(chatSockets.length);
      expect(closeLatencyMs.length, 'close 이벤트가 관측돼야 지연을 주장할 수 있다').toBeGreaterThan(0);
      expect(
        Math.min(...closeLatencyMs),
        '카드 계약: PIN 변경 뒤 활성 연결 폐기는 5초 이내(측정: 클릭 → close 이벤트)',
      ).toBeLessThanOrEqual(5_000);
    } finally {
      await context.close();
      await journey.cleanup();
    }
  });

  test('T6 새 대화는 서버에서 별개 레코드다 — 첫 대화가 폴백 id 로 합쳐지지 않는다', async ({ browser }) => {
    test.setTimeout(300_000);
    const journey = await startJourney();
    const context = await browser.newContext({ baseURL: journey.server.baseUrl });
    try {
      const page = await context.newPage();
      const firstTurn = 'NX-09 T6 첫 대화';
      const secondTurn = 'NX-09 T6 둘째 대화';
      await loginThroughUi(page);
      await page.goto('/chat');
      await pickFakeModel(page);
      await sendAndAwaitReply(page, firstTurn);
      const firstId = await conversationIdOf(page, journey.projectPath);

      // 제품 경로로 **새 대화**를 시작한다.
      await page.locator('.new-chat-row').first().click();
      await page.waitForTimeout(1_000);
      await sendAndAwaitReply(page, secondTurn);
      const secondId = await conversationIdOf(page, journey.projectPath);

      const token = await bearer(page);
      const headers = { Authorization: `Bearer ${token}` };
      const base = journey.server.baseUrl;
      const readConversation = async (id: string): Promise<string> => {
        const response = await page.request.get(
          `${base}/v1/conversations/${encodeURIComponent(id)}?project_id=default`,
          { headers, failOnStatusCode: false },
        );
        return `${response.status()} ${(await response.text()).slice(0, 800)}`;
      };
      const firstBody = await readConversation(firstId);
      const secondBody = await readConversation(secondId);

      // 저장소 파일 자체를 본다 — 서버가 실제로 몇 개의 대화를 갖고 있는가.
      const storeDir = path.join(journey.projectPath, 'conversations');
      const files = await readdirRecursive(storeDir);
      const contents = await Promise.all(files.map(async (file) => ({
        file,
        text: (await readFile(file, 'utf8')).slice(0, 4_000),
      })));
      const fallbackRecords = contents.filter((entry) => entry.text.includes('conv_unspecified'));

      await writeArtifact('t6-observation.json', {
        firstId,
        secondId,
        firstBody,
        secondBody,
        storeFiles: files.map((file) => file.replace(journey.projectPath, '<state>')),
        fallbackRecords: fallbackRecords.length,
      });

      expect(firstId, '첫 대화가 서버 폴백 id 를 자기 id 로 채택하면 안 된다')
        .not.toBe('conv_unspecified');
        expect(secondId, '새 대화는 새 식별자다').not.toBe(firstId);
      expect(firstBody).toContain('200');
      expect(firstBody, '첫 대화에 첫 턴이 있어야 한다').toContain(firstTurn);
      expect(jsonUnescape(firstBody), '둘째 대화의 턴이 첫 대화에 섮이면 안 된다').not.toContain(secondTurn);
      expect(jsonUnescape(secondBody), '둘째 대화에 둘째 턴이 있어야 한다').toContain(secondTurn);
      expect(jsonUnescape(firstBody), '첫 대화에 둘째 턴이 섮이면 안 된다').not.toContain(secondTurn);
      expect(fallbackRecords, '폴백 id 레코드가 남아 있으면 안 된다').toEqual([]);
    } finally {
      await context.close();
      await journey.cleanup();
    }
  });
});
