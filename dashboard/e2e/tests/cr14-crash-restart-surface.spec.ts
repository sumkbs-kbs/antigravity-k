/**
 * F-39 증인 (제품 경로) — **크래시·재기동 뒤 이미 열려 있는 화면**이 새 사실을 배우는가.
 *
 * 무엇을 재는가
 * -------------
 * attempt-028 은 **재기동한 서버**가 죽은 주인을 `execution_owner: dead` · `resumable: true` 로
 * 말하게 만들었고(F-36), attempt-029 는 그 서버에 도착하는 화면의 **쓰기 경로**를 고쳤다(F-37·F-38).
 * 그런데 그 둘은 **화면을 새로 여는** 경우만 덮는다. 이 증인은 처음 열린 화면이 **서버를 잃었다가
 * 되찾는 동안** 무엇을 배우는지 잰다 — 그 질문은 attempt-028/029 가 문서에 **재지 않았다고 적어 둔**
 * 자리다(F-39 후보).
 *
 * 이 파일이 재는 것과 재지 않는 것
 * --------------------------------
 * 재는 것(전부 **제품의 버튼과 화면**, 실제 PIN 로그인, 격리된 cwd):
 *
 *   M1 **세션**: 재기동이 사용자의 세션을 무효화하지 않는가 — 그렇지 않으면 질문이 바뀐다
 *      ("화면이 새 사실을 배우는가" → "사용자가 로그아웃됐는가").
 *   M2 **자동**: 화면이 **스스로** 새 사실을 배우는가 — 연결이 정상으로 돌아왔는데도 목록 행이
 *      크래시 전 스냅샷이면, 화면은 **낡은 값을 현재로 제시**한다(그 행의 라벨·버튼은 서버가
 *      말하는 사실과 달라진다).
 *   M3 **수동**: 화면이 스스로 배우지 못했다면, 사용자가 '다시 연결'을 눌렀을 때 배우는가
 *      — 아니면 그 태스크는 화면에서 **막다른 길**로 남는가.
 *
 * 재지 않는 것: **모델 실행**(실 provider — EX-01 · 태스크가 `running` 으로 남는 것이 정상 입력),
 * **프로세스 두 개의 IPC**(거부가 정직한 대답이라는 attempt-027/028 의 한계 그대로),
 * **다중 호스트**(같은 호스트의 pid 만 본다).
 *
 * 증인의 전제를 만드는 자리
 * -------------------------
 * 두 번째 서버는 **같은 상태 디렉터리**(같은 PIN 해시·같은 토큰 비밀)와 **같은 포트**로 뜬다.
 * 포트가 바뀌면 화면은 다른 origin 을 보게 되고 질문이 "죽은 서버를 보는 화면"으로 바뀐다 —
 * 그래서 하네스가 `port`·`stateDirectory` 를 받는다(`helpers/hermeticBackend.ts`).
 */

import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { expect, test } from '@playwright/test';

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
} from '../helpers/taskScreen';

const WITNESS_PROMPT = 'cr14-f39-crash-restart-witness';
const SETTLED = new Set(['연결됨', '스트림 완료', '연결 오류']);

test('크래시·재기동 뒤 열려 있는 화면이 새 사실을 배우는가 (F-39)', async ({ browser }) => {
  test.setTimeout(300_000);
  const stateDirectory = await mkdtemp(path.join(tmpdir(), 'agk-f39-'));
  await seedOpenedRegistry(stateDirectory);
  const first = await startAuthServer(1, {
    stateDirectory,
    workingDirectory: stateDirectory,
    overrides: agentBaseUrl(stateDirectory),
    removeStateOnCleanup: false,
  });
  const port = Number(new URL(first.baseUrl).port);
  const context = await browser.newContext({ baseURL: first.baseUrl });
  const page = await context.newPage();
  const violations: string[] = [];
  let second: HermeticServer | null = null;

  try {
    const readiness = await loginAndOpenAgent(page, first.baseUrl);
    if (!readiness.projectKnown) {
      violations.push('V0 전제 — 화면이 자기 프로젝트를 얻지 못한다(이 질문의 전제가 깨졌다)');
    }

    const submitted = await submitFromScreen(page, WITNESS_PROMPT);
    if (submitted.status !== 202) {
      violations.push(`V0 전제 — 제출이 접수되지 않는다(status=${submitted.status})`);
    }
    await expect(rowOf(page, WITNESS_PROMPT), '태스크 행이 그려진다').toHaveCount(1, { timeout: 20_000 });

    const beforeSurface = await readSurface(page, WITNESS_PROMPT);
    const beforeRows = (await apiTasks(page, first.baseUrl)).filter((row) => row.prompt === WITNESS_PROMPT);
    console.log(`[before] surface=${JSON.stringify(beforeSurface)}`);
    console.log(`[before] server=${JSON.stringify(beforeRows)}`);
    const tokenBefore = await bearerToken(page);

    // ── 크래시 ────────────────────────────────────────────────────────────────
    const killedPid = first.pid;
    first.kill('SIGKILL');
    await expect
      .poll(
        async () => {
          try {
            const response = await page.request.get(`${first.baseUrl}/health`);
            return response.status();
          } catch {
            return 'down';
          }
        },
        { timeout: 20_000, intervals: [200], message: '죽은 서버는 더 이상 답하지 않는다' },
      )
      .not.toBe(200);
    console.log(`[crash] SIGKILL pid=${String(killedPid)} — 첫 서버가 답하지 않는다`);

    // ── 재기동: 같은 포트 · 같은 상태 디렉터리 ───────────────────────────────
    const startedAt = Date.now();
    second = await startAuthServer(1, {
      stateDirectory,
      workingDirectory: stateDirectory,
      overrides: agentBaseUrl(stateDirectory),
      port,
      removeStateOnCleanup: false,
    });
    const restartMs = Date.now() - startedAt;
    console.log(`[restart] 같은 포트 ${port} · ${restartMs}ms · pid ${String(second.pid)}`);

    // ── M1 세션 ──────────────────────────────────────────────────────────────
    const probe = await page.request.get(`${second.baseUrl}/api/tasks`, {
      headers: { Authorization: `Bearer ${tokenBefore}` },
    });
    console.log(`[M1] 재기동 뒤 기존 토큰으로 GET /api/tasks → ${probe.status()}`);
    if (probe.status() !== 200) {
      violations.push(
        `V1 재기동이 브라우저의 세션을 무효화했다(status=${probe.status()}) — 이 증인의 질문("화면이 새 사실을 배우는가")이 "사용자가 로그아웃됐는가"로 바뀐다`,
      );
    }
    const pinAgain = await pinDialogVisible(page);
    if (pinAgain) {
      violations.push('V1 재기동 뒤 화면이 PIN 을 다시 요구한다 — 세션이 살아 있지 않다');
    }
    const sessionAlive = probe.status() === 200 && !pinAgain;
    if (!sessionAlive) {
      // 세션이 죽으면 이 질문 자체가 성립하지 않는다 — 그 사실을 이름으로 남기고 멈춘다.
      for (const violation of violations) console.log(`[VIOLATED] ${violation}`);
      console.log('[결과] FAIL — 세션이 살아 있지 않아 화면의 질문을 잴 수 없다');
      expect(violations, `F-39 위반 ${violations.length}건`).toEqual([]);
    }

    // ── M2 자동: 화면이 스스로 배우는가 ─────────────────────────────────────
    const timeline: string[] = [];
    let settled = await connectionLabel(page);
    for (let tick = 0; tick < 50; tick += 1) {
      settled = await connectionLabel(page);
      if (timeline[timeline.length - 1] !== settled) timeline.push(settled);
      if (SETTLED.has(settled) && timeline.length >= 2) break;
      await page.waitForTimeout(500);
    }
    console.log(`[M2] 연결 라벨 이력=${JSON.stringify(timeline)} · 현재=${settled}`);

    let postSurface = await readSurface(page, WITNESS_PROMPT);
    const postRows = (await apiTasks(page, second.baseUrl)).filter((row) => row.prompt === WITNESS_PROMPT);
    console.log(`[M2] surface=${JSON.stringify(postSurface)}`);
    console.log(`[M2] server=${JSON.stringify(postRows)}`);

    const compare = (surface: typeof postSurface, where: string): void => {
      if (postRows.length !== 1) {
        violations.push(`${where} 서버 목록에 그 태스크가 정확히 하나가 아니다(${postRows.length}건)`);
        return;
      }
      const expected = expectedSurface(postRows[0]);
      const mismatch =
        surface.label !== expected.label
        || surface.resume !== expected.resume
        || surface.cancel !== expected.cancel;
      console.log(`[${where}] expected=${JSON.stringify(expected)}`);
      if (mismatch) {
        violations.push(
          `${where} 화면이 서버의 현재 사실과 다르게 그린다 — 화면(label="${surface.label}" 재개=${String(surface.resume)} 취소=${String(surface.cancel)}) vs 서버(label="${expected.label}" 재개=${String(expected.resume)} 취소=${String(expected.cancel)})`,
        );
      }
    };

    if (SETTLED.has(settled) && settled !== '연결 오류') {
      // 화면이 **정상 연결**을 주장하는 순간이다: 그때의 목록은 현재 사실이어야 한다.
      compare(postSurface, 'M2');
    } else {
      // 화면이 연결을 잃었다고 말하는 순간이다 — 그렇다면 탈출구(다시 연결)가 **배우게** 해야 한다.
      if (!postSurface.retryOffered) {
        violations.push(
          `V2 화면이 연결을 잃고도(연결="${settled}") 다시 시도할 방법을 주지 않는다 — 메시지="${await messageOf(page)}"`,
        );
      } else {
        console.log('[M3] 화면이 제공한 "다시 연결"을 누른다');
        await page.getByRole('button', { name: '다시 연결' }).first().click();
        let learned = false;
        for (let tick = 0; tick < 40; tick += 1) {
          postSurface = await readSurface(page, WITNESS_PROMPT);
          const rows = (await apiTasks(page, second.baseUrl)).filter(
            (row) => row.prompt === WITNESS_PROMPT,
          );
          if (rows.length === 1) {
            const expected = expectedSurface(rows[0]);
            if (
              postSurface.label === expected.label
              && postSurface.resume === expected.resume
              && postSurface.cancel === expected.cancel
            ) {
              learned = true;
              break;
            }
          }
          await page.waitForTimeout(500);
        }
        console.log(`[M3] 다시 연결 뒤 학습=${String(learned)} surface=${JSON.stringify(postSurface)}`);
        if (!learned) compare(postSurface, 'M3');
      }
    }

    for (const violation of violations) console.log(`[VIOLATED] ${violation}`);
    console.log(`[결과] ${violations.length === 0 ? 'OK' : `FAIL — 위반 ${violations.length}건`}`);
    expect(violations, `F-39 위반 ${violations.length}건`).toEqual([]);
  } finally {
    await context.close();
    if (second !== null) await second.cleanup();
    await first.cleanup();
    await rm(stateDirectory, { recursive: true, force: true });
  }
});
