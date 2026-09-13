import type { TaskSummary } from './taskExecutionSchema';

/**
 * 태스크 목록에서 **무엇을 할 수 있는가** — 규칙은 이 파일 한 곳이 소유한다.
 *
 * F-36: 서버는 `execution_owner`(그 실행 주인이 지금 살아 있는가)와 `resumable`(이 행에 대해
 * `POST /resume` 이 성공할 것인가)을 말한다. 화면이 그 사실을 **상태 문자열만 보고 추측**하면,
 * 크래시 뒤 재시작한 서버가 `running` 이라고 말하는 고아 태스크에서 복구 버튼이 사라진다 —
 * 실제로는 서버가 재개를 받아주는데도(200) 화면은 취소만 제안했다.
 *
 * 서버가 필드를 보내지 않으면(`undefined`) 예전 상태 규칙으로 되돌아간다: 그 경우는 이 화면보다
 * 오래된 서버를 상대하는 것이고, 없는 정보를 추측으로 대체하지 않는다.
 */
const LEGACY_RESUMABLE_STATUSES: ReadonlySet<string> = new Set(['failed', 'paused', 'cancelled']);

const CANCELLABLE_STATUSES: ReadonlySet<string> = new Set(['pending', 'running', 'resuming']);

export function canResumeTask(task: Pick<TaskSummary, 'status' | 'resumable'>): boolean {
  if (task.resumable !== undefined) return task.resumable;
  return LEGACY_RESUMABLE_STATUSES.has(task.status);
}

export function canCancelTask(task: Pick<TaskSummary, 'status'>): boolean {
  return CANCELLABLE_STATUSES.has(task.status);
}

/** 주인이 죽은 비종결 태스크 — 서버는 이 행을 여전히 `running` 이라고 부른다. */
export function isOrphanedTask(
  task: Pick<TaskSummary, 'status' | 'execution_owner'>,
): boolean {
  return task.execution_owner === 'dead' && CANCELLABLE_STATUSES.has(task.status);
}

/**
 * 화면에 말할 상태 — **저장된 상태가 지금 사실인지**를 함께 말한다.
 *
 * `running` + 죽은 주인은 \"실행 중\"이 아니다: 아무도 실행하지 않고 있고, 재개하면 이어서 돌릴 수
 * 있다. 이 라벨은 그 사실을 사용자와 스크린리더에게 같이 말한다(aria-label 도 이 값을 쓴다).
 */
export function taskStateLabel(
  task: Pick<TaskSummary, 'status' | 'execution_owner' | 'resumable'>,
): string {
  if (!isOrphanedTask(task)) return task.status;
  return canResumeTask(task) ? '실행 중단(소유 프로세스 종료) — 재개 가능' : '실행 중단(소유 프로세스 종료)';
}
