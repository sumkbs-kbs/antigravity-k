/**
 * F-39 계약 — **서버를 잃었다가 되찾으면 목록을 다시 읽는다.**
 *
 * 무엇을 재는가
 * -------------
 * `useTaskExecutionEvents` 는 서버의 두 자료를 묶는다: **목록**(한 번 읽은 스냅샷 — 그 안에
 * `status`·`execution_owner`·`resumable` 처럼 시간에 따라 변하는 값이 들어 있다)과 **스트림**(선택한
 * 태스크의 이벤트, 스스로 다시 붙는다). 스트림이 다시 붙어도 목록이 새로워지지 않으면 화면은
 * **낡은 스냅샷을 현재라고 말하면서** 연결됨을 표시한다 — 실물 증인
 * `dashboard/e2e/tests/cr14-crash-restart-surface.spec.ts` 가 그 상태를 쟀다(고침 전: 화면은
 * `running`·재개 없음, 서버는 `dead`·재개 가능, 연결은 `연결됨`).
 *
 * 이 파일은 그 규칙을 **단위로** 고정한다(실 브라우저 증인은 느리고, 이 규칙은 여기서 자란다):
 *   ① 재연결 뒤 목록을 다시 읽는다        — 고침의 본체
 *   ② 스트림이 실패하지 않으면 다시 읽지 않는다 — 거짓 양성 0(불필요한 재조회는 화면을 흔든다)
 *   ③ 다시 읽기가 실패하면 **조용히 넘기지 않는다** — 낡은 목록을 조용히 들고 있으면 그 병이 돌아온다
 *
 * 무엇을 재지 않는가
 * ------------------
 * - **서버의 진실**은 여기서 재지 않는다: 그 값이 무엇이어야 하는지는 실서버 계약(F-36 의
 *   `tests/test_cr14_task_orphan_surface.py`)과 실물 증인이 소유한다. 여기서 재는 것은 **언제
 *   다시 읽는가**이다.
 * - **실제 네트워크·프로세스**는 없다(그것은 e2e 증인의 몫이다).
 */

import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TaskSummarySchema } from './taskExecutionSchema';

const api = vi.hoisted(() => ({
  fetchTaskList: vi.fn(),
  fetchTaskEvents: vi.fn(),
  streamTaskEvents: vi.fn(),
  submitTask: vi.fn(),
  cancelTask: vi.fn(),
  resumeTask: vi.fn(),
  forkTask: vi.fn(),
}));

vi.mock('./taskExecutionApi', () => api);

const { useTaskExecutionEvents } = await import('./useTaskExecutionEvents');

/** 서버가 주는 모양 그대로 만든다 — 스키마가 소유하는 규칙(브랜드·기본값)을 우회하지 않는다. */
function summary(executionOwner: 'live' | 'dead', resumable: boolean) {
  return TaskSummarySchema.parse({
    task_id: 'task-1',
    prompt: 'cr14-f39-unit-witness',
    status: 'running',
    error: null,
    created_at: '2026-01-01T00:00:00+00:00',
    updated_at: '2026-01-01T00:00:00+00:00',
    execution_owner: executionOwner,
    resumable,
  });
}

const LIVE = summary('live', false);
const ORPHANED = summary('dead', true);

beforeEach(() => {
  window.localStorage.clear();
  api.fetchTaskList.mockReset();
  api.fetchTaskEvents.mockReset();
  api.streamTaskEvents.mockReset();
  api.fetchTaskEvents.mockResolvedValue({ events: [], lastSequence: 0 });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useTaskExecutionEvents — 재연결 뒤 목록', () => {
  it('스트림이 끊겼다가 다시 붙으면 목록을 다시 읽고 새 사실을 반영한다', async () => {
    api.fetchTaskList.mockResolvedValueOnce([LIVE]).mockResolvedValueOnce([ORPHANED]);
    api.streamTaskEvents
      .mockRejectedValueOnce(new Error('스트림이 끊겼다'))
      .mockResolvedValueOnce({ lastSequence: 0 });

    const { result } = renderHook(() => useTaskExecutionEvents());

    await waitFor(() => expect(result.current.tasks[0]?.execution_owner).toBe('dead'), {
      timeout: 5_000,
      interval: 50,
    });
    expect(api.fetchTaskList).toHaveBeenCalledTimes(2);
    // 목록을 다시 읽는 것은 **스트림을 다시 시작시키지 않는다** — 그렇지 않으면 재시작 루프가 된다.
    expect(api.streamTaskEvents).toHaveBeenCalledTimes(2);
    expect(result.current.tasks[0]?.resumable).toBe(true);
  });

  it('스트림이 끊기지 않으면 목록을 다시 읽지 않는다', async () => {
    api.fetchTaskList.mockResolvedValue([LIVE]);
    api.streamTaskEvents.mockResolvedValue({ lastSequence: 0 });

    const { result } = renderHook(() => useTaskExecutionEvents());
    await waitFor(() => expect(result.current.tasks).toHaveLength(1), { timeout: 5_000 });
    // 재연결 대기(`waitForReconnect`, 1초)보다 **더 오래** 기다린다: 잘못된 재조회가 있다면 그 안에
    // 드러난다. 연결 상태로 기다리지 않는 이유는 이 테스트가 **재조회 여부**를 재기 때문이다
    // (즉시 resolve 하는 mock 에서는 커밋 뒤의 `loading` 타이머가 상태를 덮어쓴다 — 그 타이머는
    // 실제 네트워크 왕복보다 먼저 도는 것이 정상이고, 그래서 이 파일은 상태 대신 **호출 수**를 잰다).
    await new Promise((resolve) => setTimeout(resolve, 1_500));
    expect(api.fetchTaskList).toHaveBeenCalledTimes(1);
    expect(api.streamTaskEvents).toHaveBeenCalledTimes(1);
  });

  it('목록을 다시 읽지 못하면 조용히 넘기지 않고 화면에 말한다', async () => {
    api.fetchTaskList
      .mockResolvedValueOnce([LIVE])
      .mockRejectedValueOnce(new Error('목록을 다시 읽지 못했다'));
    api.streamTaskEvents
      .mockRejectedValueOnce(new Error('스트림이 끊겼다'))
      .mockResolvedValueOnce({ lastSequence: 0 });

    const { result } = renderHook(() => useTaskExecutionEvents());

    await waitFor(() => expect(result.current.error).toBe('목록을 다시 읽지 못했다'), {
      timeout: 5_000,
      interval: 50,
    });
    // 낡은 목록을 조용히 들고 있지 않다 = 그 사실이 화면의 상태로 드러난다.
    expect(result.current.tasks[0]?.execution_owner).toBe('live');
  });
});
