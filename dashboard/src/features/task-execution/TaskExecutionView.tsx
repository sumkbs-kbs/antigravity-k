import { AgentTree, ExecutionChecklist, TerminalEventList } from './TaskExecutionSections';
import { projectTaskExecution } from './taskExecutionProjection';
import { TaskIdSchema, type TaskEvent, type TaskId, type TaskSummary } from './taskExecutionSchema';
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
  onSelectTask: (taskId: TaskId) => void;
  onRetry: () => void;
}>;

function taskLabel(task: TaskSummary): string {
  const prompt = task.prompt.trim();
  return prompt.length > 0 ? prompt : task.task_id;
}

export function TaskExecutionView({
  tasks,
  selectedTaskId,
  events,
  connectionState,
  error,
  onSelectTask,
  onRetry,
}: TaskExecutionViewProps) {
  const projection = selectedTaskId === null ? null : projectTaskExecution(selectedTaskId, events);
  const handleSelection = (value: string): void => {
    const parsed = TaskIdSchema.safeParse(value);
    if (parsed.success) onSelectTask(parsed.data);
  };

  return (
    <section className="task-execution-shell glass-panel" aria-labelledby="task-execution-title" aria-busy={connectionState === 'loading'}>
      <header className="task-execution-header">
        <div>
          <h3 id="task-execution-title">실행 추적</h3>
          <p>versioned event replay와 live stream을 한 task 경계에서 표시합니다.</p>
        </div>
        <div className="task-execution-controls">
          <label htmlFor="task-execution-select">Task 실행</label>
          <select
            id="task-execution-select"
            value={selectedTaskId ?? ''}
            onChange={(event) => handleSelection(event.currentTarget.value)}
            disabled={tasks.length === 0}
          >
            {tasks.length === 0 && <option value="">실행 기록 없음</option>}
            {tasks.map((task) => <option key={task.task_id} value={task.task_id}>{taskLabel(task)}</option>)}
          </select>
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
          <div className="task-execution-grid">
            <AgentTree agents={projection.agents} />
            <ExecutionChecklist items={projection.checklist} />
          </div>
          <TerminalEventList terminals={projection.terminals} />
        </>
      ) : null}
    </section>
  );
}
