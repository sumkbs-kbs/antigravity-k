import { useState, type FormEvent } from 'react';

import type { TaskId, TaskSummary } from './taskExecutionSchema';

export type PendingTaskAction =
  | Readonly<{ kind: 'submit' }>
  | Readonly<{ taskId: TaskId; kind: 'cancel' | 'resume' | 'fork' }>;

type TaskQueuePanelProps = Readonly<{
  tasks: readonly TaskSummary[];
  selectedTaskId: TaskId | null;
  pendingAction: PendingTaskAction | null;
  onSelectTask: (taskId: TaskId) => void;
  onSubmit: (prompt: string) => void;
  onCancel: (taskId: TaskId) => void;
  onResume: (taskId: TaskId) => void;
  onFork: (taskId: TaskId) => void;
}>;

function taskTitle(task: TaskSummary): string {
  const prompt = task.prompt.trim();
  return prompt.length > 0 ? prompt : task.task_id;
}

export function TaskQueuePanel({
  tasks,
  selectedTaskId,
  pendingAction,
  onSelectTask,
  onSubmit,
  onCancel,
  onResume,
  onFork,
}: TaskQueuePanelProps) {
  const [prompt, setPrompt] = useState('');
  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const normalized = prompt.trim();
    if (normalized.length === 0) return;
    onSubmit(normalized);
    setPrompt('');
  };

  return (
    <section className="task-queue" aria-labelledby="task-queue-title">
      <header>
        <div>
          <h4 id="task-queue-title">Task Queue</h4>
          <span>{tasks.length}개 실행</span>
        </div>
      </header>
      <form className="task-submit-form" onSubmit={handleSubmit}>
        <label htmlFor="task-submit-prompt">새 작업 지시</label>
        <div>
          <input
            id="task-submit-prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.currentTarget.value)}
            placeholder="실행할 작업을 입력하세요"
            disabled={pendingAction?.kind === 'submit'}
          />
          <button type="submit" disabled={prompt.trim().length === 0 || pendingAction?.kind === 'submit'}>
            {pendingAction?.kind === 'submit' ? '제출 중' : '작업 제출'}
          </button>
        </div>
      </form>
      <div className="task-history-heading">
        <h5>세션 히스토리</h5>
        <span>{tasks.length}개 세션</span>
      </div>
      <ul className="task-queue-list">
        {tasks.map((task) => {
          const title = taskTitle(task);
          const isPending = pendingAction !== null
            && 'taskId' in pendingAction
            && pendingAction.taskId === task.task_id;
          return (
            <li key={task.task_id} className={task.task_id === selectedTaskId ? 'is-selected' : undefined}>
              <button
                className="task-queue-select"
                type="button"
                onClick={() => onSelectTask(task.task_id)}
                aria-label={`${title}, 상태 ${task.status}`}
              >
                <strong>{title}</strong>
                <span>{task.status}</span>
              </button>
              <div className="task-queue-actions">
                {(task.status === 'pending' || task.status === 'running' || task.status === 'resuming') && (
                  <button type="button" disabled={isPending} onClick={() => onCancel(task.task_id)} aria-label={`${title} 취소`}>
                    취소
                  </button>
                )}
                {(task.status === 'failed' || task.status === 'paused' || task.status === 'cancelled') && (
                  <button type="button" disabled={isPending} onClick={() => onResume(task.task_id)} aria-label={`${title} 재개`}>
                    재개
                  </button>
                )}
                <button type="button" disabled={isPending} onClick={() => onFork(task.task_id)} aria-label={`${title} 분기`}>
                  {pendingAction?.kind === 'fork' && isPending ? '분기 중' : '분기'}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
