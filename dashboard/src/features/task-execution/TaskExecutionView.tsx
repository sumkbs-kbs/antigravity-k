import { ApprovalQueue } from './ApprovalQueue';
import type { ApprovalDecision, ApprovalRequest } from './approvalApi';
import { ExecutionBlockRenderer } from './ExecutionBlockRenderer';
import { projectTaskExecution } from './taskExecutionProjection';
import { TaskQueuePanel, type PendingTaskAction } from './TaskQueuePanel';
import type { TaskEvent, TaskId, TaskSummary } from './taskExecutionSchema';
import type { TaskConnectionState } from './useTaskExecutionEvents';

const CONNECTION_LABELS = {
  idle: '대기',
  loading: '불러오는 중',
  connected: '연결됨',
  reconnecting: '재연결 중',
  complete: '스트림 완료',
  error: '연결 오류',
} as const satisfies Record<TaskConnectionState, string>;

export type TaskExecutionViewProps = Readonly<{
  tasks: readonly TaskSummary[];
  selectedTaskId: TaskId | null;
  events: readonly TaskEvent[];
  connectionState: TaskConnectionState;
  error: string | null;
  pendingAction: PendingTaskAction | null;
  approvals: readonly ApprovalRequest[];
  pendingApprovalId: string | null;
  approvalError: string | null;
  onSelectTask: (taskId: TaskId) => void;
  onSubmit: (prompt: string) => void;
  onCancel: (taskId: TaskId) => void;
  onResume: (taskId: TaskId) => void;
  onFork: (taskId: TaskId) => void;
  onResolveApproval: (requestId: string, decision: ApprovalDecision) => void;
  onRetry: () => void;
}>;

export function TaskExecutionView({
  tasks,
  selectedTaskId,
  events,
  connectionState,
  error,
  pendingAction,
  approvals,
  pendingApprovalId,
  approvalError,
  onSelectTask,
  onSubmit,
  onCancel,
  onResume,
  onFork,
  onResolveApproval,
  onRetry,
}: TaskExecutionViewProps) {
  const projection = selectedTaskId === null ? null : projectTaskExecution(selectedTaskId, events);

  return (
    <section className="task-execution-shell glass-panel" aria-labelledby="task-execution-title" aria-busy={connectionState === 'loading'}>
      <header className="task-execution-header">
        <div>
          <h3 id="task-execution-title">실행 추적</h3>
          <p>versioned event replay와 live stream을 한 task 경계에서 표시합니다.</p>
        </div>
        <div className="task-execution-controls">
          <span className={`task-connection-state task-connection-${connectionState}`} role="status" aria-live="polite">
            {CONNECTION_LABELS[connectionState]}
          </span>
        </div>
      </header>

      {error !== null && (
        <div className="task-execution-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={onRetry}>다시 연결</button>
        </div>
      )}

      <div className="task-workbench-grid">
        <TaskQueuePanel
          tasks={tasks}
          selectedTaskId={selectedTaskId}
          pendingAction={pendingAction}
          onSelectTask={onSelectTask}
          onSubmit={onSubmit}
          onCancel={onCancel}
          onResume={onResume}
          onFork={onFork}
        />
        <ApprovalQueue
          approvals={approvals}
          pendingRequestId={pendingApprovalId}
          error={approvalError}
          onResolve={onResolveApproval}
        />
      </div>

      {tasks.length === 0 && connectionState !== 'loading' ? (
        <div className="task-execution-zero">표시할 task 실행 기록이 없습니다.</div>
      ) : connectionState === 'loading' && selectedTaskId === null ? (
        <div className="task-execution-skeleton" aria-label="task 실행 기록 불러오는 중">
          <span />
          <span />
          <span />
        </div>
      ) : projection !== null ? (
        <>
          <div className="task-execution-summary">
            <span>{events.length} events</span>
            <span>last sequence {projection.lastSequence}</span>
          </div>
          <ExecutionBlockRenderer projection={projection} />
        </>
      ) : null}
    </section>
  );
}
