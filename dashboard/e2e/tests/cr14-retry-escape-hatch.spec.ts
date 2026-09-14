/**
 * F-41 증인 (제품 경로) — **화면이 연결을 포기한 뒤** 사용자가 누르는 '다시 연결'이 새 사실을 배우는가.
 *
 * 무엇을 재는가
 * -------------
 * attempt-030 은 **열려 있는 화면**이 서버를 잃었다가 되찾으면 목록을 다시 읽게 만들었고(F-39),
 * 그 증인은 **M2(자동)** 가 참이 되어 **M3(수동 탈출구)** 분기를 타지 않았다 — 그 사실을 그 attempt
 * 가 자기 한계로 적었다. 이 증인은 **M3 만** 잰다.
 *
 * 전제를 어떻게 만드는가 (이 자리가 이 증인의 전부다)
 * --------------------------------------------------
 * M3 를 발화시키려면 화면이 **스스로 자동 재연결을 포기한 상태**여야 한다. 그래서:
 *
 *   1. 서버를 띄우고, 실제 PIN 로그인을 하고, 제품의 제출 폼으로 태스크를 만든다.
 *   2. 서버를 **그룹째 SIGKILL** 한다(런처만 죽이면 서버가 살아남는다 — F-40).
 *   3. **재기동하지 않고 기다린다** — 화면이 `연결 오류` 라고 말하고 '다시 연결'을 내놓을 때까지.
 *   4. **서버가 없는 동안** 탈출구를 눌러 본다 — 눌러도 화면이 **막다른 길**이 되지 않는가.
 *   5. **그 뒤에** 서버를 같은 포트·같은 상태 디렉터리로 다시 띄운다 — 이제 그 태스크의 주인은
 *      죽었고 서버는 `execution_owner: dead` · `resumable: true` 라고 말한다.
 *   6. '다시 연결'을 누르고, 화면이 **서버의 현재 사실**을 그리는지 잰다.
 *   7. **그 뒤에 새 태스크를 제출하고**(제품 경로 — 그 순간 화면의 스냅샷은 새 태스크를 `running`
 *      으로 본다) 크래시·재기동을 반복한다. 탈출구는 **한 번만** 통하는 문이 아니어야 한다.
 *
 * 재는 것
 * -------
 *   V1 전제 — 화면이 `연결 오류` 를 말하고 '다시 연결'을 내놓는다(아니면 이 질문은 성립하지 않는다).
 *   V1b 탈출구가 **막다른 길이 아니다** — 서버가 없는 동안 눌러도 화면이 다시 시도할 수 있는
 *       상태(오류 + 탈출구)로 남는다. 여기서 탈출구가 사라지면 사용자는 구제 수단을 잃는다.
 *   V2 탈출구가 **동작한다** — 재기동 뒤 누르면 화면의 행이 서버의 현재 사실과 같아진다.
 *   V3 탈출구가 **연결 라벨도 되돌린다** — 누른 뒤 라벨이 오류 상태로 남지 않는다.
 *   V4 전제 — 세션이 살아 있다(재기동이 로그아웃을 만들면 질문이 바뀐다).
 *   V5 탈출구는 **반복해서** 쓸 수 있다 — 두 번째 크래시·재기동에서도 V2·V3 이 다시 참이다.
 *
 * 이빨(고침이 아니라 **자가 거짓말하지 않는지**를 먼저 확인했다)
 * ------------------------------------------------------------------
 * 이 증인의 첫 두 실행은 **자를 탓해야** 했다: ① 두 번째 구제에서 화면의 행이 이미 서버와 같아
 * (두 번재 크래시가 사실을 바꾸지 않았다) 배울 것이 없었고, ② 연결 라벨을 **전이 중**에 읽었다
 * (`연결 오류 → 불러오는 중 → …`). 그래서 2회차는 **새 태스크를 제출**해 낡은 스냅샷을 만들고,
 * 라벨은 **정착할 때까지** 기다린 뒤에 읽는다. 자가 제품보다 먼저 틀릴 수 있다는 것을 적어 둔다.
 *
 * 재지 않는 것
 * ------------
 *   - **모델 실행**(실 provider — EX-01): 태스크가 `running` 으로 남는 것이 정상 입력이다.
 *   - **다른 클라이언트·다른 주인**이 만든 변화는 이 증인의 자극이 아니다(목록의 신선도는
 *     재연결과 사용자의 행동에서만 갱신된다 — 그 경계는 경계 문서가 소유한다).
 *   - **다중 호스트**, **자동 재연결의 횟수 정책**(3회 시도가 실제로 3회인가는 단위 계약
 *     `useTaskExecutionEvents.test.ts` 가 잰다).
 */

import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { startAuthServer, type HermeticServer } from '../helpers/hermeticBackend';
import {
  agentBaseUrl,
  apiTasks,
  bearerToken,
  connectionLabel,
  expectedSurface,
  loginAndOpenAgent,
  messageOf,
  pinDialogVisible,
  readSurface,
  rowOf,
  seedOpenedRegistry,
  submitFromScreen,
  type TaskRow,
} from '../helpers/taskScreen';

const WITNESS_PROMPT = 'cr14-f41-retry-escape-hatch-witness';
const SECOND_PROMPT = 'cr14-f41-retry-escape-hatch-witness-2';

/** 화면이 스스로 포기했다고 말하는 상태 — 이 증인의 **전제**다. */
const GAVE_UP = '연결 오류';
/** 화면이 서버와 정상으로 붙어 있다고 말하는 **정착** 상태들(탈출구가 되돌려야 하는 상태). */
const HEALTHY = new Set(['연결됨', '스트림 완료', '대기']);

/** 화면이 스스로 포기할 때까지 기다린다 — 자동 재연결이 끝나야 M3 가 발화한다. */
async function waitForGiveUp(page: Page, prompt: string, violations: string[], tag: string): Promise<void> {
  const timeline: string[] = [];
  let label = await connectionLabel(page);
  let retryOffered = false;
  for (let tick = 0; tick < 60; tick += 1) {
    label = await connectionLabel(page);
    if (timeline[timeline.length - 1] !== label) timeline.push(label);
    retryOffered = (await readSurface(page, prompt)).retryOffered;
    if (label === GAVE_UP && retryOffered) break;
    await page.waitForTimeout(500);
  }
  console.log(`[${tag}] 연결 라벨 이력=${JSON.stringify(timeline)} · 현재=${label} · 탈출구=${String(retryOffered)}`);
  console.log(`[${tag}] 메시지="${await messageOf(page)}"`);
  if (label !== GAVE_UP) {
    violations.push(`${tag} V1 전제 — 화면이 스스로 포기하지 않았다(라벨 이력=${JSON.stringify(timeline)})`);
  }
  if (!retryOffered) {
    violations.push(`${tag} V1 전제 — 화면이 연결을 잃었는데 "다시 연결"을 주지 않는다(막다른 길)`);
  }
}

/**
 * 탈출구를 누르고 **정착한 라벨**과 **서버와 같은 행**을 기다린다.
 *
 * 라벨은 전이 중일 수 있으므로(`연결 오류 → 불러오는 중 → 연결됨`) 정착 값만 판정한다 — 첫 실행이
 * 전이 중의 값을 위반으로 읽었고, 그것은 제품이 아니라 자의 결함이었다.
 */
async function pressRetryAndExpectLearning(
  page: Page,
  prompt: string,
  serverRow: TaskRow,
  violations: string[],
  tag: string,
): Promise<void> {
  const before = await readSurface(page, prompt);
  await page.getByRole('button', { name: '다시 연결' }).first().click();

  const timeline: string[] = [];
  let settled = '';
  let leftError = false;
  for (let tick = 0; tick < 60; tick += 1) {
    const label = await connectionLabel(page);
    if (timeline[timeline.length - 1] !== label) timeline.push(label);
    if (HEALTHY.has(label)) {
      settled = label;
      break;
    }
    if (label === GAVE_UP) {
      // 누르기 **전**의 상태를 정착으로 읽지 않는다: 오류를 **떠난 뒤** 다시 오류면 실패다.
      if (leftError) {
        settled = label;
        break;
      }
    } else {
      leftError = true;
    }
    await page.waitForTimeout(250);
  }
  if (settled === '') settled = await connectionLabel(page);

  const expected = expectedSurface(serverRow);
  let surface = await readSurface(page, prompt);
  let learned = false;
  for (let tick = 0; tick < 40; tick += 1) {
    surface = await readSurface(page, prompt);
    if (
      surface.label === expected.label
      && surface.resume === expected.resume
      && surface.cancel === expected.cancel
    ) {
      learned = true;
      break;
    }
    await page.waitForTimeout(250);
  }

  console.log(`[${tag}] 탈출구 누르기 전 surface=${JSON.stringify(before)}`);
  console.log(`[${tag}] 연결 라벨 이력=${JSON.stringify(timeline)} · 정착=${settled}`);
  console.log(`[${tag}] surface=${JSON.stringify(surface)}`);
  console.log(`[${tag}] expected=${JSON.stringify(expected)}`);
  console.log(`[${tag}] 낡은 스냅샷이었는가=${String(!sameFacts(before, expected))}`);

  if (!learned) {
    violations.push(
      `${tag} V2 탈출구가 새 사실을 배우지 못했다 — 화면(label="${surface.label}" 재개=${String(surface.resume)} 취소=${String(surface.cancel)}) vs 서버(label="${expected.label}" 재개=${String(expected.resume)} 취소=${String(expected.cancel)})`,
    );
  }
  if (settled === GAVE_UP) {
    violations.push(`${tag} V3 탈출구 뒤에도 화면이 연결 오류라고 말한다`);
  } else if (!HEALTHY.has(settled)) {
    violations.push(`${tag} V3 탈출구 뒤 연결 라벨이 정상 상태로 정착하지 않는다(이력=${JSON.stringify(timeline)})`);
  }
}

/** 표면이 **서버가 말하는 사실**과 같은가 — 전이 중의 잡음이 아니라 사실만 본다. */
function sameFacts(
  surface: Readonly<{ label: string; resume: boolean; cancel: boolean }>,
  expected: Readonly<{ label: string; resume: boolean; cancel: boolean }>,
): boolean {
  return surface.label === expected.label && surface.resume === expected.resume && surface.cancel === expected.cancel;
}

test('연결을 포기한 화면의 "다시 연결"이 새 사실을 배우는가 (F-41)', async ({ browser }) => {
  test.setTimeout(300_000);
  const stateDirectory = await mkdtemp(path.join(tmpdir(), 'agk-f41-'));
  await seedOpenedRegistry(stateDirectory);
  const serverOptions = {
    stateDirectory,
    workingDirectory: stateDirectory,
    overrides: agentBaseUrl(stateDirectory),
    removeStateOnCleanup: false,
  };
  const servers: HermeticServer[] = [];
  const first = await startAuthServer(1, serverOptions);
  servers.push(first);
  const port = Number(new URL(first.baseUrl).port);
  const context = await browser.newContext({ baseURL: first.baseUrl });
  const page = await context.newPage();
  const violations: string[] = [];

  /** 같은 포트·같은 상태 디렉터리로 재기동한다(= 같은 PIN 해시·같은 토큰 비밀). */
  const restart = async (tag: string): Promise<HermeticServer> => {
    const startedAt = Date.now();
    const next = await startAuthServer(1, { ...serverOptions, port });
    servers.push(next);
    console.log(`[${tag}] 같은 포트 ${port} 로 재기동 · ${Date.now() - startedAt}ms · pid ${String(next.pid)}`);
    return next;
  };
  /** 재기동이 세션을 살려 두었는지 — 아니면 질문이 "사용자가 로그아웃됐는가"로 바뀐다. */
  const expectSessionAlive = async (server: HermeticServer, token: string, tag: string): Promise<void> => {
    const probe = await page.request.get(`${server.baseUrl}/api/tasks`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (probe.status() !== 200) {
      violations.push(`${tag} V4 전제 — 재기동이 브라우저의 세션을 무효화했다(status=${probe.status()})`);
    }
    if (await pinDialogVisible(page)) {
      violations.push(`${tag} V4 전제 — 재기동 뒤 화면이 PIN 을 다시 요구한다`);
    }
  };
  const rowFrom = async (baseUrl: string, prompt: string, tag: string): Promise<TaskRow | null> => {
    const rows = (await apiTasks(page, baseUrl)).filter((row) => row.prompt === prompt);
    console.log(`[${tag}] 서버 행=${JSON.stringify(rows)}`);
    if (rows.length !== 1) {
      violations.push(`${tag} 서버 목록에 그 태스크가 정확히 하나가 아니다(${rows.length}건)`);
      return null;
    }
    return rows[0];
  };
  const submitAndWait = async (prompt: string, tag: string): Promise<void> => {
    const submitted = await submitFromScreen(page, prompt);
    console.log(`[${tag}] 제출 status=${submitted.status}`);
    if (submitted.status !== 202) {
      violations.push(`${tag} 제출이 접수되지 않는다(status=${submitted.status})`);
    }
    await expect(rowOf(page, prompt), `${tag} 태스크 행이 그려진다`).toHaveCount(1, { timeout: 20_000 });
  };

  try {
    const readiness = await loginAndOpenAgent(page, first.baseUrl);
    if (!readiness.projectKnown) {
      violations.push('V0 전제 — 화면이 자기 프로젝트를 얻지 못한다(이 질문의 전제가 깨졌다)');
    }
    await submitAndWait(WITNESS_PROMPT, 'submit-1');
    const tokenBefore = await bearerToken(page);
    console.log(`[before] surface=${JSON.stringify(await readSurface(page, WITNESS_PROMPT))}`);

    // ── 1회차 크래시: 재기동하지 **않는다** (자동 재연결이 포기해야 M3 가 발화한다) ──────────
    first.kill('SIGKILL');
    console.log(`[crash-1] SIGKILL pid=${String(first.pid)} — 포트 ${port} 가 닫힌다`);
    await waitForGiveUp(page, WITNESS_PROMPT, violations, 'down-1');

    // ── V1b: 서버가 **없는 동안** 탈출구를 눌러 본다 — 막다른 길이 되면 안 된다 ──────────────
    await page.getByRole('button', { name: '다시 연결' }).first().click();
    let hopeless = await readSurface(page, WITNESS_PROMPT);
    for (let tick = 0; tick < 40; tick += 1) {
      hopeless = await readSurface(page, WITNESS_PROMPT);
      if (hopeless.connection === GAVE_UP && hopeless.retryOffered) break;
      await page.waitForTimeout(500);
    }
    console.log(`[hopeless-retry] surface=${JSON.stringify(hopeless)}`);
    if (hopeless.connection !== GAVE_UP) {
      violations.push(
        `V1b 탈출구를 눌렀더니 연결 라벨이 "${hopeless.connection}" 이다 — 서버가 없는데 정상이라고 말한다`,
      );
    }
    if (!hopeless.retryOffered) {
      violations.push('V1b 서버가 없는 동안 탈출구를 눌렀더니 탈출구가 사라졌다(사용자가 구제 수단을 잃는다)');
    }

    // ── 재기동 뒤 탈출구: 1회차 ────────────────────────────────────────────────────────────
    const second = await restart('restart-1');
    await expectSessionAlive(second, tokenBefore, 'restart-1');
    const rowAfterFirst = await rowFrom(second.baseUrl, WITNESS_PROMPT, 'server-1');
    if (rowAfterFirst !== null) {
      await pressRetryAndExpectLearning(page, WITNESS_PROMPT, rowAfterFirst, violations, 'M3-1');
    }

    // ── 2회차: **새 태스크를 제출**해 화면의 스냅샷을 다시 낡게 만든다(그러지 않으면 배울 것이 없다)
    await submitAndWait(SECOND_PROMPT, 'submit-2');
    console.log(`[before-2] surface=${JSON.stringify(await readSurface(page, SECOND_PROMPT))}`);

    second.kill('SIGKILL');
    console.log(`[crash-2] SIGKILL pid=${String(second.pid)} — 포트 ${port} 가 닫힌다`);
    await waitForGiveUp(page, SECOND_PROMPT, violations, 'down-2');
    const third = await restart('restart-2');
    await expectSessionAlive(third, tokenBefore, 'restart-2');
    const rowAfterSecond = await rowFrom(third.baseUrl, SECOND_PROMPT, 'server-2');
    if (rowAfterSecond !== null) {
      await pressRetryAndExpectLearning(page, SECOND_PROMPT, rowAfterSecond, violations, 'M3-2');
    }

    for (const violation of violations) console.log(`[VIOLATED] ${violation}`);
    console.log(`[결과] ${violations.length === 0 ? 'OK' : `FAIL — 위반 ${violations.length}건`}`);
    expect(violations, `F-41 위반 ${violations.length}건`).toEqual([]);
  } finally {
    await context.close();
    for (const server of servers) await server.cleanup();
    await rm(stateDirectory, { recursive: true, force: true });
  }
});
