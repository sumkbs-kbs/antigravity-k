/**
 * F-37 · F-38 증인 (제품 경로) — 대시보드의 **"작업 제출"** 은 서버에 도착하는가.
 *
 * 무엇을 재는가
 * -------------
 * 와이어 증인(`attempt-029/repro/f37_submit_identity_witness.py`)은 **본문의 모양**을 재고,
 * 이 파일은 **제품의 그 버튼**을 누른다: 격리된 실 서버 + 실제 PIN 로그인 + `/agent` 화면의 제출 폼.
 *
 * 두 결함은 서로를 가리므로 **다른 기계 상태**에서 각각 잰다(서버의 cwd 를 격리하면 레지스트리도
 * 격리된다 — 프로젝트 레지스트리는 상대 경로 `data/projects.json` 이다):
 *
 *   1) **알고 있는 프로젝트**가 있는 기계(F-37): 레지스트리를 미리 심어 `last_accessed_at` 이
 *      실재하는 문자열이 되게 한다. 화면은 프로젝트를 알고 제출하며, 그 제출이 서버의 모델에서
 *      **422**(`Extra inputs are not permitted: body -> project_id`)로 막혔다.
 *   2) **처음 설치한 기계**(F-38): 레지스트리가 비어 있으면 서버는 기본 프로젝트를
 *      `last_accessed_at: null` 로 직렬화하고, 화면의 스키마(`.optional()`)는 `null` 을 거부한다.
 *      파싱이 실패하면 스토어가 비고 — 화면은 프로젝트를 **모르는 채로** — 제출은 정체성 없이
 *      나간다(서버: `missing_execution_context` 400).
 *
 * 두 상태 어디에서도 버튼이 성공하지 못했다 — 그래서 이 증인은 한 번의 실행이 아니라
 * **두 기계 상태**로 잰다: 고침 전 **위반 5건**(알고 있는 프로젝트 쪽 3 = F-37 · 처음 설치한
 * 기계 쪽 2 = F-38) / 고침 후 0(두 테스트 각각 `exit 0`).
 *
 * 다음 질문(이 attempt 가 **재지 않은 것**)
 * -----------------------------------------
 * 크래시 뒤 **이미 열려 있는 화면**이 새 사실을 배우는가 — 그 질문의 준비(실 서버 + 실 로그인 +
 * 실 제출 + **격리된 cwd** + 고정 포트)는 이 파일이 이미 만들어 두었다. 가설은 "목록 조회가
 * `reloadVersion` 에만 매여 있어 스트림이 다시 붙어도 크래시 전 스냅샷이 남는다"이고, **가설은
 * 측정이 아니다**. 이 자리를 "테스트 단위로 비활성화한 껍데기"로 두지 않은 이유가 있다: 그런 표기는
 * `scripts/gate_skip_register.json` 이 소유하는데, 그 등록부의 채널은 **게이트 스킵**이라 대시보드
 * 소스의 표기를 소유할 자리가 없다(`tests/test_cr14_gate_skip_register.py` 의 tripwire 가 그 사실을
 * 지킨다 — 재지 않은 질문을 소유자 없는 스킵으로 만들지 않는다). 그래서 재지 않은 질문은 이 주석·
 * 증거팩·§6 재개 순서에 적었다(질문 자체를 감추지는 않는다).
 *
 * 무엇을 재지 않는가
 * ------------------
 * - **모델 실행**은 재지 않는다(실 provider — EX-01). 태스크가 `running` 으로 남는 것이 정상 입력이다.
 * - **서버의 저장 구조**는 재지 않는다(와이어 증인·pytest 계약·대시보드 스키마 계약이 판다).
 */

import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { authPin, startAuthServer } from '../helpers/hermeticBackend';

const WITNESS_PROMPT = 'cr14-f37-submit-witness';

type TaskRow = Readonly<{
  task_id: string;
  prompt: string;
  status: string;
  execution_owner?: string;
  resumable?: boolean;
}>;

type Surface = Readonly<{
  label: string;
  cancel: boolean;
  resume: boolean;
  connection: string;
  retryOffered: boolean;
}>;

type ScreenReadiness = Readonly<{
  /** 화면이 자기 프로젝트를 알고 있는가(`agk_active_project_id` 를 **이 로드에서** 썼는가). */
  projectKnown: boolean;
  /** 서버가 준 프로젝트 목록의 원문(파싱 실패의 근거를 로그에 남기기 위해). */
  projectsBody: string;
}>;

type Submission = Readonly<{
  status: number;
  body: string;
  /** 화면이 실제로 보낸 것 — 정체성이 본문 어디에 실렸는지. */
  sent: Readonly<{ projectHeader: string | null; body: Record<string, unknown> }>;
}>;

/**
 * 프로젝트 레지스트리를 **미리 심는다**(서버의 cwd 아래 `data/projects.json`).
 *
 * `last_accessed_at` 이 문자열인 레코드가 있어야 화면의 스키마가 목록을 파싱한다 — 이 상태가
 * "이미 프로젝트를 쓰고 있는 기계"이고, F-37 이 사는 자리다.
 */
async function seedOpenedRegistry(workingDirectory: string): Promise<void> {
  await mkdir(path.join(workingDirectory, 'data'), { recursive: true });
  await writeFile(
    path.join(workingDirectory, 'data', 'projects.json'),
    JSON.stringify(
      [
        {
          id: 'default',
          name: 'agk-f37-opened',
          path: workingDirectory,
          is_active: true,
          last_accessed_at: '2026-01-05T09:00:00.000000',
          tasks: [],
        },
      ],
      null,
      2,
    ),
    { encoding: 'utf8' },
  );
}

async function bearerToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => sessionStorage.getItem('ag_access_token'));
  if (token === null || token === '') throw new Error('화면이 세션 토큰을 갖고 있지 않다');
  return token;
}

async function apiTasks(page: Page, baseUrl: string): Promise<readonly TaskRow[]> {
  const response = await page.request.get(`${baseUrl}/api/tasks`, {
    headers: { Authorization: `Bearer ${await bearerToken(page)}` },
  });
  expect(response.status(), 'GET /api/tasks 는 화면과 같은 자격으로 물어야 한다').toBe(200);
  const body = (await response.json()) as { data?: readonly TaskRow[] };
  return body.data ?? [];
}

/** 그 프롬프트의 행(화면은 프롬프트를 제목으로 그린다 — aria-label 에는 태스크 ID 가 없다). */
function rowOf(page: Page, prompt: string) {
  return page.locator('.task-queue-list li').filter({ hasText: prompt });
}

/** 화면이 그 행에 대해 그리는 것 — 라벨과 버튼의 존재, 연결 라벨. */
async function readSurface(page: Page, prompt: string): Promise<Surface> {
  const item = rowOf(page, prompt);
  const label = (await item.locator('.task-queue-select span').first().innerText()).trim();
  const connection = (await page.locator('.task-connection-state').first().innerText()).trim();
  const actions = item.locator('.task-queue-actions');
  return {
    label,
    cancel: (await actions.getByRole('button', { name: '취소' }).count()) > 0,
    resume: (await actions.getByRole('button', { name: '재개' }).count()) > 0,
    connection,
    retryOffered: (await page.getByRole('button', { name: '다시 연결' }).count()) > 0,
  };
}

/** 실제 PIN 로그인 + 원하는 화면이 뜰 때까지 기다린다(우회하지 않는다). */
async function openScreen(page: Page, probe: ReturnType<Page['locator']>, why: string): Promise<void> {
  const pinDialog = page.locator('[role="dialog"][aria-label="PIN 인증"]');
  for (let attempt = 0; attempt < 30; attempt += 1) {
    if ((await probe.count()) > 0) return;
    if ((await pinDialog.count()) > 0) {
      await pinDialog.locator('input').first().fill(authPin);
      await pinDialog.getByRole('button', { name: /잠금 해제|확인/ }).first().click();
      await expect(pinDialog, `${why} — PIN 해제`).toHaveCount(0, { timeout: 15_000 });
      continue;
    }
    await page.waitForTimeout(500);
  }
  throw new Error(`${why} — 화면이 뜨지 않았다`);
}

/**
 * 로그인하고 `/agent` 를 연 뒤 **화면이 자기 프로젝트를 얻었는지**를 돌려준다.
 *
 * 정체성은 `hydrateFromServer` → `/api/projects` → `agk_active_project_id` 로 스토어에 들어온다.
 * `addInitScript` 가 매 내비게이션 시작에 그 키를 지우므로, 값이 있다는 것은 **이 페이지 로드가**
 * 하이드레이션을 끝냈고 그 프로젝트가 실재한다는 뜻이다(다른 로드의 잔재가 아니다).
 */
async function loginAndOpenAgent(page: Page, baseUrl: string): Promise<ScreenReadiness> {
  await page.addInitScript(() => {
    try {
      window.localStorage.removeItem('agk_active_project_id');
    } catch {
      /* private mode / quota — 이 증인의 전제는 화면이 정체성을 얻는 것이므로 실패로 드러난다 */
    }
  });
  let projectsBody = '';
  page.on('response', (response) => {
    if (!response.url().includes('/api/projects')) return;
    void response.text()
      .then((text) => {
        if (text) projectsBody = text.slice(0, 600);
      })
      .catch(() => undefined);
  });

  await page.goto('/');
  await openScreen(page, page.locator('.sidebar, nav').first(), '첫 화면');
  await page.goto(`${baseUrl}/agent`);
  await openScreen(page, page.getByLabel('새 작업 지시'), '/agent 화면');

  let projectKnown = false;
  try {
    await expect
      .poll(
        async () => page.evaluate(() => window.localStorage.getItem('agk_active_project_id')),
        { timeout: 15_000, intervals: [250] },
      )
      .not.toBeNull();
    projectKnown = true;
  } catch {
    projectKnown = false;
  }
  return { projectKnown, projectsBody };
}

/** 화면의 제출 폼을 실제로 눌러 **보낸 것과 받은 것**을 함께 기록한다. */
async function submitFromScreen(page: Page, prompt: string): Promise<Submission> {
  const field = page.getByLabel('새 작업 지시');
  await field.fill(prompt);
  const responsePromise = page.waitForResponse((response) => response.url().includes('/api/tasks/submit'));
  const requestPromise = page.waitForRequest((request) => request.url().includes('/api/tasks/submit'));
  await page.getByRole('button', { name: '작업 제출' }).click();
  const request = await requestPromise;
  const response = await responsePromise;
  return {
    status: response.status(),
    body: (await response.text()).slice(0, 300),
    sent: {
      projectHeader: request.headers()['x-agk-project-id'] ?? null,
      body: request.postDataJSON() as Record<string, unknown>,
    },
  };
}

function agentBaseUrl(stateDirectory: string): Readonly<Record<string, string>> {
  return {
    AGK_TASK_DB_PATH: path.join(stateDirectory, 'tasks.db'),
    AGK_ALLOWED_ROOTS: stateDirectory,
  };
}

test('작업 제출이 서버에 도착하고 목록에 나타난다 (F-37)', async ({ browser }) => {
  test.setTimeout(150_000);
  const stateDirectory = await mkdtemp(path.join(tmpdir(), 'agk-f37-'));
  await seedOpenedRegistry(stateDirectory);
  const server = await startAuthServer(1, {
    stateDirectory,
    workingDirectory: stateDirectory,
    overrides: agentBaseUrl(stateDirectory),
  });
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const violations: string[] = [];

  try {
    const readiness = await loginAndOpenAgent(page, server.baseUrl);
    console.log(`[projects] ${readiness.projectsBody}`);
    if (!readiness.projectKnown) {
      violations.push('V0 이 슬라이스의 전제가 깨졌다 — 화면이 프로젝트를 알고 있어야 제출 본문을 잰다');
    }

    const submitted = await submitFromScreen(page, WITNESS_PROMPT);
    console.log(`[sent] ${JSON.stringify(submitted.sent)}`);
    console.log(`[submit] status=${submitted.status} body=${submitted.body}`);
    if (submitted.status !== 202) {
      violations.push(
        `V1 화면의 제출이 서버에서 거부된다 — status=${submitted.status} body=${submitted.body}`,
      );
    }

    const row = rowOf(page, WITNESS_PROMPT);
    let appeared = false;
    try {
      await expect(row, '화면이 그 태스크를 목록에 그린다').toHaveCount(1, { timeout: 20_000 });
      appeared = true;
    } catch {
      appeared = false;
    }
    if (!appeared) {
      violations.push('V2 202 를 받았는데 화면의 목록에 그 태스크가 나타나지 않는다');
    } else {
      console.log(`[surface] ${JSON.stringify(await readSurface(page, WITNESS_PROMPT))}`);
    }

    // 목록은 화면의 재료다 — 서버도 같은 사실을 말하는지(접수만 되고 사라지지 않았는지) 본다.
    const mine = (await apiTasks(page, server.baseUrl)).filter((task) => task.prompt === WITNESS_PROMPT);
    console.log(`[api] rows=${JSON.stringify(mine)}`);
    if (mine.length !== 1) {
      violations.push(`V3 서버 목록에 그 태스크가 정확히 하나가 아니다(${mine.length}건)`);
    } else if (mine[0].execution_owner !== 'live') {
      violations.push(
        `V3 접수된 태스크의 실행 주인이 'live' 가 아니다(execution_owner=${String(mine[0].execution_owner)})`,
      );
    }

    for (const violation of violations) console.log(`[VIOLATED] ${violation}`);
    console.log(`[결과] ${violations.length === 0 ? 'OK' : `FAIL — 위반 ${violations.length}건`}`);
    expect(violations, `F-37 위반 ${violations.length}건`).toEqual([]);
  } finally {
    await context.close();
    await server.cleanup();
    await rm(stateDirectory, { recursive: true, force: true });
  }
});

test('처음 설치한 기계에서도 화면이 자기 프로젝트를 얻고 제출한다 (F-38)', async ({ browser }) => {
  test.setTimeout(150_000);
  const stateDirectory = await mkdtemp(path.join(tmpdir(), 'agk-f38-'));
  // 레지스트리를 **심지 않는다**: 서버가 기본 프로젝트를 만들고, 그 레코드의
  // `last_accessed_at` 은 `null` 이다 — 화면의 스키마가 거부하던 바로 그 값이다.
  const server = await startAuthServer(1, {
    stateDirectory,
    workingDirectory: stateDirectory,
    overrides: agentBaseUrl(stateDirectory),
  });
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const violations: string[] = [];

  try {
    const readiness = await loginAndOpenAgent(page, server.baseUrl);
    console.log(`[projects] ${readiness.projectsBody}`);
    if (!readiness.projectKnown) {
      violations.push(
        'V0 화면이 자기 프로젝트를 얻지 못했다 — `/api/projects` 를 읽고도 스토어가 비어 있다'
        + `(원문: ${readiness.projectsBody.slice(0, 300)})`,
      );
    }

    // 결과는 화면이 아니라 **서버의 응답**으로 잰다: 프로젝트를 모르는 화면의 제출은
    // 정체성 없이 나가고 서버가 `missing_execution_context` 로 거부한다.
    const submitted = await submitFromScreen(page, WITNESS_PROMPT);
    console.log(`[sent] ${JSON.stringify(submitted.sent)}`);
    console.log(`[submit] status=${submitted.status} body=${submitted.body}`);
    if (submitted.status !== 202) {
      violations.push(
        `V1 처음 설치한 기계에서 제출이 거부된다 — status=${submitted.status} body=${submitted.body}`,
      );
    }

    for (const violation of violations) console.log(`[VIOLATED] ${violation}`);
    console.log(`[결과] ${violations.length === 0 ? 'OK' : `FAIL — 위반 ${violations.length}건`}`);
    expect(violations, `F-38 위반 ${violations.length}건`).toEqual([]);
  } finally {
    await context.close();
    await server.cleanup();
    await rm(stateDirectory, { recursive: true, force: true });
  }
});
