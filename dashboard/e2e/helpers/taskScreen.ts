/**
 * Task 화면(`/agent`)을 **제품 경로로** 재는 e2e 도우미.
 *
 * 왜 파일이 따로 있는가
 * ---------------------
 * attempt-029 는 이 도우미들을 `cr14-task-submit-contract.spec.ts` 안에 두었다(그때는 증인이
 * 하나였다). attempt-030 은 **같은 화면에 다른 질문**(크래시·재기동 뒤 열려 있는 화면이 새 사실을
 * 배우는가)을 하므로, 두 증인이 같은 자를 쓴다 — 질문마다 도우미를 복사하면 **재는 자가 갈라지고**,
 * 갈라진 재는 자는 같은 사실을 다른 값으로 보고할 수 있다.
 *
 * 이 파일이 지키는 것 (증인의 **전제**는 여기서 만들어진다)
 * --------------------------------------------------------
 * - **실 서버 + 실제 PIN 로그인**: 인증을 우회하지 않는다(`startAuthServer` + `loginAndOpenAgent`).
 * - **격리된 cwd**: 프로젝트 레지스트리(`data/projects.json`)는 상대 경로라 서버의 cwd 를 따라간다 —
 *   `workingDirectory` 를 격리해야 "처음 설치한 기계"를 **만들 수** 있다(F-38 의 전제).
 * - **같은 상태 디렉터리 재사용**: 크래시·재시작 슬라이스가 두 번째 프로세스에 같은 PIN 해시·토큰
 *   비밀을 넘긴다(그러지 않으면 질문이 "인증 실패"로 바뀐다).
 * - **화면이 실제로 보낸 것**을 기록한다(추측하지 않는다).
 */

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { expect, type Locator, type Page } from '@playwright/test';

import { authPin } from './hermeticBackend';

export const WITNESS_TASK_DB = 'tasks.db';

export type TaskRow = Readonly<{
  task_id: string;
  prompt: string;
  status: string;
  execution_owner?: string;
  resumable?: boolean;
}>;

export type Surface = Readonly<{
  label: string;
  cancel: boolean;
  resume: boolean;
  connection: string;
  retryOffered: boolean;
}>;

export type ScreenReadiness = Readonly<{
  /** 화면이 자기 프로젝트를 알고 있는가(`agk_active_project_id` 를 **이 로드에서** 썼는가). */
  projectKnown: boolean;
  /** 서버가 준 프로젝트 목록의 원문(파싱 실패의 근거를 로그에 남기기 위해). */
  projectsBody: string;
}>;

export type Submission = Readonly<{
  status: number;
  body: string;
  /** 화면이 실제로 보낸 것 — 정체성이 본문 어디에 실렸는지. */
  sent: Readonly<{ projectHeader: string | null; body: Record<string, unknown> }>;
}>;

/**
 * 프로젝트 레지스트리를 **미리 심는다**(서버의 cwd 아래 `data/projects.json`).
 *
 * `last_accessed_at` 이 문자열인 레코드가 있어야 화면의 스키마가 목록을 파싱한다 — 이 상태가
 * "이미 프로젝트를 쓰고 있는 기계"이다(F-37 이 사는 자리).
 */
export async function seedOpenedRegistry(workingDirectory: string): Promise<void> {
  await mkdir(path.join(workingDirectory, 'data'), { recursive: true });
  await writeFile(
    path.join(workingDirectory, 'data', 'projects.json'),
    JSON.stringify(
      [
        {
          id: 'default',
          name: 'agk-e2e-opened',
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

/** 서버 프로세스에 넘길 격리 값 — 첫 서버와 두 번째 서버에 **같은 값**을 넘겨야 한다. */
export function agentBaseUrl(stateDirectory: string): Readonly<Record<string, string>> {
  return {
    AGK_TASK_DB_PATH: path.join(stateDirectory, WITNESS_TASK_DB),
    AGK_ALLOWED_ROOTS: stateDirectory,
  };
}

export async function bearerToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => sessionStorage.getItem('ag_access_token'));
  if (token === null || token === '') throw new Error('화면이 세션 토큰을 갖고 있지 않다');
  return token;
}

/** 화면과 **같은 자격**으로 서버에 묻는다 — 화면이 무엇을 그리는지의 기준이다. */
export async function apiTasks(page: Page, baseUrl: string): Promise<readonly TaskRow[]> {
  const response = await page.request.get(`${baseUrl}/api/tasks`, {
    headers: { Authorization: `Bearer ${await bearerToken(page)}` },
  });
  expect(response.status(), 'GET /api/tasks 는 화면과 같은 자격으로 물어야 한다').toBe(200);
  const body = (await response.json()) as { data?: readonly TaskRow[] };
  return body.data ?? [];
}

/** 그 프롬프트의 행(화면은 프롬프트를 제목으로 그린다 — aria-label 에는 태스크 ID 가 없다). */
export function rowOf(page: Page, prompt: string): Locator {
  return page.locator('.task-queue-list li').filter({ hasText: prompt });
}

/** 화면이 그 행에 대해 그리는 것 — 라벨과 버튼의 존재, 연결 라벨. */
export async function readSurface(page: Page, prompt: string): Promise<Surface> {
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

export async function connectionLabel(page: Page): Promise<string> {
  return (await page.locator('.task-connection-state').first().innerText()).trim();
}

export async function messageOf(page: Page): Promise<string> {
  const banner = page.locator('.task-execution-error span').first();
  return (await banner.count()) > 0 ? (await banner.innerText()).trim() : '';
}

/**
 * 실제 PIN 로그인 + 원하는 화면이 뜰 때까지 기다린다(우회하지 않는다).
 */
export async function openScreen(page: Page, probe: Locator, why: string): Promise<void> {
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

/** 화면이 지금 PIN 모달을 요구하고 있는가(재기동 뒤 세션이 살아 있는지의 눈금). */
export async function pinDialogVisible(page: Page): Promise<boolean> {
  return (await page.locator('[role="dialog"][aria-label="PIN 인증"]').count()) > 0;
}

/**
 * 로그인하고 `/agent` 를 연 뒤 **화면이 자기 프로젝트를 얻었는지**를 돌려준다.
 *
 * 정체성은 `hydrateFromServer` → `/api/projects` → `agk_active_project_id` 로 스토어에 들어온다.
 * `addInitScript` 가 매 내비게이션 시작에 그 키를 지우므로, 값이 있다는 것은 **이 페이지 로드가**
 * 하이드레이션을 끝냈고 그 프로젝트가 실재한다는 뜻이다(다른 로드의 잔재가 아니다).
 */
export async function loginAndOpenAgent(page: Page, baseUrl: string): Promise<ScreenReadiness> {
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
export async function submitFromScreen(page: Page, prompt: string): Promise<Submission> {
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

const CANCELLABLE_STATUSES = new Set(['pending', 'running', 'resuming']);
const LEGACY_RESUMABLE_STATUSES = new Set(['failed', 'paused', 'cancelled']);

/**
 * 서버의 행이 **그 행에 대해 약속하는 것** — 증인은 이 기대를 서버에서 직접 만든다.
 *
 * 제품 규칙(`taskLifecycleActions.ts`)을 그대로 옮겨 적는 이유: 여기서 재는 것이 "화면이 그 규칙을
 * 따르는가"이기 때문이다. 규칙의 정의는 제품이 소유하고(단위 계약이 그것을 잰다 — F-36 의 계약),
 * 증인은 **서버가 말하는 사실**로부터 기대값을 만든다.
 */
export function expectedSurface(row: TaskRow): Readonly<{ label: string; resume: boolean; cancel: boolean }> {
  const orphaned = row.execution_owner === 'dead' && CANCELLABLE_STATUSES.has(row.status);
  const resumable = row.resumable === undefined
    ? LEGACY_RESUMABLE_STATUSES.has(row.status)
    : row.resumable;
  const label = orphaned
    ? resumable
      ? '실행 중단(소유 프로세스 종료) — 재개 가능'
      : '실행 중단(소유 프로세스 종료)'
    : row.status;
  return { label, resume: resumable, cancel: CANCELLABLE_STATUSES.has(row.status) };
}
