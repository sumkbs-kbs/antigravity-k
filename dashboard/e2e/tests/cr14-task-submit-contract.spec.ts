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
 * 다음 질문은 **다른 파일**이 이어받았다
 * ---------------------------------------
 * 크래시 뒤 **이미 열려 있는 화면**이 새 사실을 배우는가 — attempt-029 는 그 질문을 **재지 않았고**
 * (증인 파일 안에 테스트 단위 비활성화 표기로 자리를 남기려다 게이트가 두 번 정당하게 거부했다),
 * 그 자리는 `cr14-crash-restart-surface.spec.ts`(attempt-030)가 이어받았다. 두 파일이 같은 자를
 * 쓰도록 도우미는 `../helpers/taskScreen` 이 소유한다 — 질문마다 자를 복사하면 재는 자가 갈라진다.
 *
 * 무엇을 재지 않는가
 * ------------------
 * - **모델 실행**은 재지 않는다(실 provider — EX-01). 태스크가 `running` 으로 남는 것이 정상 입력이다.
 * - **서버의 저장 구조**는 재지 않는다(와이어 증인·pytest 계약·대시보드 스키마 계약이 판다).
 */

import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { expect, test } from '@playwright/test';

import { startAuthServer } from '../helpers/hermeticBackend';
import {
  agentBaseUrl,
  apiTasks,
  loginAndOpenAgent,
  readSurface,
  rowOf,
  seedOpenedRegistry,
  submitFromScreen,
} from '../helpers/taskScreen';

const WITNESS_PROMPT = 'cr14-f37-submit-witness';

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
