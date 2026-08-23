import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TaskExecutionView } from './TaskExecutionView';
import { TaskEventSchema, TaskIdSchema, TaskSummarySchema } from './taskExecutionSchema';

const taskId = TaskIdSchema.parse('task-live');
const task = TaskSummarySchema.parse({
  task_id: 'task-live',
  prompt: 'Repository tests and repair',
  status: 'running',
  output: '',
  error: null,
  created_at: '2026-08-20T09:00:00Z',
  updated_at: '2026-08-20T09:00:01Z',
  completed_at: null,
});
const leadEvent = TaskEventSchema.parse({
  sequence: 1,
  schema_version: 1,
  task_id: 'task-live',
  step_id: 'plan',
  agent_id: 'lead-agent',
  parent_id: null,
  tool_call_id: null,
  approval_id: null,
  resource_job_id: null,
  correlation_id: 'run-live',
  event_type: 'agent.started',
  payload: {
    agent_name: 'Lead agent',
    title: 'Plan verification',
  },
  created_at: '2026-08-20T09:00:01Z',
});
const event = TaskEventSchema.parse({
  sequence: 2,
  schema_version: 1,
  task_id: 'task-live',
  step_id: 'verify',
  agent_id: 'qa-agent',
  parent_id: 'lead-agent',
  tool_call_id: 'tool-qa',
  approval_id: null,
  resource_job_id: null,
  correlation_id: 'run-live',
  event_type: 'tool.running',
  payload: {
    agent_name: 'QA agent',
    title: 'Run verification',
    tool_name: 'terminal',
    command: 'npm run build',
    stdout: 'building dashboard',
  },
  created_at: '2026-08-20T09:00:02Z',
});

describe('TaskExecutionView', () => {
  it('renders a clear empty state when no task runs exist', () => {
    render(
      <TaskExecutionView
        tasks={[]}
        selectedTaskId={null}
        events={[]}
        connectionState="idle"
        error={null}
        pendingAction={null}
        approvals={[]}
        pendingApprovalId={null}
        approvalError={null}
        onSelectTask={vi.fn()}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        onResume={vi.fn()}
        onFork={vi.fn()}
        onResolveApproval={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: '실행 추적' })).toBeInTheDocument();
    expect(screen.getByText('표시할 task 실행 기록이 없습니다.')).toBeInTheDocument();
  });

  it('renders agent, checklist, and terminal evidence from the selected task', () => {
    render(
      <TaskExecutionView
        tasks={[task]}
        selectedTaskId={taskId}
        events={[leadEvent, event]}
        connectionState="connected"
        error={null}
        pendingAction={null}
        approvals={[]}
        pendingApprovalId={null}
        approvalError={null}
        onSelectTask={vi.fn()}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        onResume={vi.fn()}
        onFork={vi.fn()}
        onResolveApproval={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Repository tests and repair, 상태 running' })).toBeInTheDocument();
    expect(screen.getByText('QA agent')).toBeInTheDocument();
    expect(screen.getByText('Run verification')).toBeInTheDocument();
    expect(screen.getByText('npm run build')).toBeInTheDocument();
    expect(screen.getByText('building dashboard')).toBeInTheDocument();
    expect(screen.getByText('연결됨')).toBeInTheDocument();

    const leadNode = screen.getByText('Lead agent').closest('li');
    expect(leadNode).not.toBeNull();
    if (leadNode !== null) {
      expect(within(leadNode).getByText('QA agent')).toBeInTheDocument();
    }
  });
});
