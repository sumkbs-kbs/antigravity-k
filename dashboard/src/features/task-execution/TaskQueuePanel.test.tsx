import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TaskQueuePanel } from './TaskQueuePanel';
import { TaskIdSchema, TaskSummarySchema } from './taskExecutionSchema';

const runningTask = TaskSummarySchema.parse({
  task_id: 'task-running',
  prompt: '검증 작업 실행',
  status: 'running',
  error: null,
  created_at: '2026-08-22T09:00:00Z',
  updated_at: '2026-08-22T09:00:01Z',
});
const failedTask = TaskSummarySchema.parse({
  task_id: 'task-failed',
  prompt: '중단 지점부터 복구',
  status: 'failed',
  error: 'interrupted',
  created_at: '2026-08-22T08:00:00Z',
  updated_at: '2026-08-22T08:00:01Z',
});

describe('TaskQueuePanel', () => {
  it('submits trimmed prompts and exposes only valid lifecycle actions', () => {
    const onSubmit = vi.fn();
    const onCancel = vi.fn();
    const onResume = vi.fn();
    const onFork = vi.fn();

    render(
      <TaskQueuePanel
        tasks={[runningTask, failedTask]}
        selectedTaskId={TaskIdSchema.parse('task-running')}
        pendingAction={null}
        onSelectTask={vi.fn()}
        onSubmit={onSubmit}
        onCancel={onCancel}
        onResume={onResume}
        onFork={onFork}
      />,
    );

    fireEvent.change(screen.getByLabelText('새 작업 지시'), { target: { value: '  테스트를 실행해줘  ' } });
    fireEvent.click(screen.getByRole('button', { name: '작업 제출' }));
    expect(onSubmit).toHaveBeenCalledWith('테스트를 실행해줘');

    fireEvent.click(screen.getByRole('button', { name: '검증 작업 실행 취소' }));
    expect(onCancel).toHaveBeenCalledWith(TaskIdSchema.parse('task-running'));
    expect(screen.queryByRole('button', { name: '검증 작업 실행 재개' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '중단 지점부터 복구 재개' }));
    expect(onResume).toHaveBeenCalledWith(TaskIdSchema.parse('task-failed'));
    expect(screen.queryByRole('button', { name: '중단 지점부터 복구 취소' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '중단 지점부터 복구 분기' }));
    expect(onFork).toHaveBeenCalledWith(TaskIdSchema.parse('task-failed'));
    expect(screen.getByRole('heading', { name: '세션 히스토리' })).toBeInTheDocument();
  });
});
