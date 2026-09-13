import { describe, expect, it } from 'vitest';

import { canCancelTask, canResumeTask, isOrphanedTask, taskStateLabel } from './taskLifecycleActions';
import { TaskSummarySchema } from './taskExecutionSchema';

function summary(overrides: Record<string, unknown>) {
  return TaskSummarySchema.parse({
    task_id: 'task-fixture',
    prompt: '검증 작업',
    status: 'running',
    error: null,
    created_at: '2026-09-14T00:00:00Z',
    updated_at: '2026-09-14T00:00:01Z',
    ...overrides,
  });
}

describe('taskLifecycleActions (F-36)', () => {
  it('believes the server when it says the task is resumable', () => {
    // 크래시 뒤 재시작한 서버는 이 행을 여전히 `running` 이라고 부르지만 주인은 죽었다.
    const orphaned = summary({ execution_owner: 'dead', resumable: true });

    expect(isOrphanedTask(orphaned)).toBe(true);
    expect(canResumeTask(orphaned)).toBe(true);
    expect(canCancelTask(orphaned)).toBe(true);
    expect(taskStateLabel(orphaned)).toBe('실행 중단(소유 프로세스 종료) — 재개 가능');
  });

  it('does not offer resume for a run that this process is executing', () => {
    const live = summary({ execution_owner: 'live', resumable: false });

    expect(isOrphanedTask(live)).toBe(false);
    expect(canResumeTask(live)).toBe(false);
    expect(canCancelTask(live)).toBe(true);
    expect(taskStateLabel(live)).toBe('running');
  });

  it('falls back to the status rule only when the server said nothing', () => {
    const legacyFailed = summary({ status: 'failed' });
    const legacyRunning = summary({ status: 'running' });

    expect(legacyFailed.resumable).toBeUndefined();
    expect(canResumeTask(legacyFailed)).toBe(true);
    expect(canResumeTask(legacyRunning)).toBe(false);
  });

  it('does not invent resumability the server denied', () => {
    // 실패했지만 체크포인트가 없는 행 — 서버는 `resumable: false` 라고 말한다(재개는 404).
    const noCheckpoint = summary({ status: 'failed', resumable: false });

    expect(canResumeTask(noCheckpoint)).toBe(false);
    expect(isOrphanedTask(noCheckpoint)).toBe(false);
    expect(taskStateLabel(noCheckpoint)).toBe('failed');
  });

  it('keeps terminal rows out of both actions unless the server allows resume', () => {
    const done = summary({ status: 'done', execution_owner: 'none', resumable: false });

    expect(canCancelTask(done)).toBe(false);
    expect(canResumeTask(done)).toBe(false);
  });
});
