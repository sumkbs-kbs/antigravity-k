import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ExecutionBlockRenderer } from './ExecutionBlockRenderer';
import { buildExecutionBlocks } from './executionBlocks';
import { projectTaskExecution } from './taskExecutionProjection';
import { TaskEventSchema, TaskIdSchema } from './taskExecutionSchema';

const taskId = TaskIdSchema.parse('task-blocks');
const event = TaskEventSchema.parse({
  sequence: 1,
  schema_version: 2,
  task_id: 'task-blocks',
  step_id: 'verify',
  agent_id: 'qa-agent',
  parent_id: null,
  tool_call_id: 'tool-build',
  approval_id: null,
  resource_job_id: null,
  correlation_id: 'run-blocks',
  event_type: 'tool.running',
  payload: {
    agent_name: 'QA agent',
    title: 'Build dashboard',
    tool_name: 'terminal',
    command: 'npm run build',
    stdout: 'building',
  },
  created_at: '2026-08-22T09:00:00Z',
});

describe('ExecutionBlockRenderer', () => {
  it('builds a stable typed block order from the event projection', () => {
    const blocks = buildExecutionBlocks(projectTaskExecution(taskId, [event]));

    expect(blocks.map((block) => block.kind)).toEqual(['agents', 'checklist', 'terminals']);
    expect(blocks[2]).toMatchObject({ kind: 'terminals', terminals: [{ id: 'tool-build' }] });
  });

  it('renders every projected evidence block through semantic regions', () => {
    render(<ExecutionBlockRenderer projection={projectTaskExecution(taskId, [event])} />);

    expect(screen.getByRole('heading', { name: '에이전트 트리' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '실행 체크리스트' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '터미널 이벤트' })).toBeInTheDocument();
    expect(screen.getByText('building')).toBeInTheDocument();
  });
});
