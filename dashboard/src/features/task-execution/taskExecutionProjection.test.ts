import { describe, expect, it } from 'vitest';

import { TaskEventSchema, TaskIdSchema, TaskSummarySchema } from './taskExecutionSchema';
import { boundTerminalOutput, projectTaskExecution } from './taskExecutionProjection';

const taskA = TaskIdSchema.parse('task-a');

describe('projectTaskExecution', () => {
  it('accepts the compact task-list shape returned by the runtime', () => {
    const task = TaskSummarySchema.parse({
      task_id: 'task-a',
      prompt: 'Compact task record',
      status: 'done',
      error: null,
      created_at: '2026-08-20T09:00:00Z',
      updated_at: '2026-08-20T09:00:01Z',
    });

    expect(task.output).toBe('');
    expect(task.completed_at).toBeNull();
  });

  it('isolates one task and preserves agent hierarchy, checklist order, and tool output', () => {
    const events = [
      TaskEventSchema.parse({
        sequence: 1,
        schema_version: 1,
        task_id: 'task-a',
        step_id: 'plan',
        agent_id: 'lead',
        parent_id: null,
        tool_call_id: null,
        approval_id: null,
        resource_job_id: null,
        correlation_id: 'run-a',
        event_type: 'agent.started',
        payload: { agent_name: 'Lead agent', title: 'Plan repository changes' },
        created_at: '2026-08-20T09:00:00Z',
      }),
      TaskEventSchema.parse({
        sequence: 2,
        schema_version: 1,
        task_id: 'task-a',
        step_id: 'edit',
        agent_id: 'worker',
        parent_id: 'lead',
        tool_call_id: 'tool-1',
        approval_id: null,
        resource_job_id: null,
        correlation_id: 'run-a',
        event_type: 'tool.started',
        payload: { agent_name: 'Code worker', tool_name: 'terminal', command: 'npm test' },
        created_at: '2026-08-20T09:00:01Z',
      }),
      TaskEventSchema.parse({
        sequence: 1,
        schema_version: 1,
        task_id: 'task-b',
        step_id: 'foreign',
        agent_id: 'other',
        parent_id: null,
        tool_call_id: null,
        approval_id: null,
        resource_job_id: null,
        correlation_id: 'run-b',
        event_type: 'agent.started',
        payload: { agent_name: 'Other task agent' },
        created_at: '2026-08-20T09:00:01Z',
      }),
      TaskEventSchema.parse({
        sequence: 3,
        schema_version: 1,
        task_id: 'task-a',
        step_id: 'edit',
        agent_id: 'worker',
        parent_id: 'lead',
        tool_call_id: 'tool-1',
        approval_id: null,
        resource_job_id: null,
        correlation_id: 'run-a',
        event_type: 'tool.completed',
        payload: { tool_name: 'terminal', stdout: '24 tests passed' },
        created_at: '2026-08-20T09:00:02Z',
      }),
    ];

    const projection = projectTaskExecution(taskA, events);

    expect(projection.agents.map((agent) => agent.id)).toEqual(['lead', 'worker']);
    expect(projection.agents.map((agent) => agent.depth)).toEqual([0, 1]);
    expect(projection.agents[1]?.status).toBe('completed');
    expect(projection.checklist.map((item) => item.id)).toEqual(['plan', 'edit']);
    expect(projection.checklist[1]?.status).toBe('completed');
    expect(projection.terminals).toHaveLength(1);
    expect(projection.terminals[0]?.command).toBe('npm test');
    expect(projection.terminals[0]?.output).toContain('24 tests passed');
    expect(projection.lastSequence).toBe(3);
  });

  it('keeps the head and tail when terminal output exceeds the display budget', () => {
    const output = `${'A'.repeat(18)}${'B'.repeat(18)}`;

    expect(boundTerminalOutput(output, 24)).toBe(
      `${'A'.repeat(12)}\n\n[12 characters omitted]\n\n${'B'.repeat(12)}`,
    );
  });
});

describe('CTX-03 compress outcome status mapping', () => {
  it('maps compress success/degrade/halt to completed/degraded/failed', () => {
    const events = [
      TaskEventSchema.parse({
        sequence: 1,
        schema_version: 2,
        task_id: 'task-a',
        step_id: 'compress-ok',
        agent_id: null,
        parent_id: null,
        tool_call_id: null,
        approval_id: null,
        resource_job_id: null,
        correlation_id: null,
        event_type: 'context.compress.succeeded',
        payload: { outcome: 'success', strategy: 'summarize', digest: 'abc' },
        created_at: '2026-09-06T00:00:00Z',
      }),
      TaskEventSchema.parse({
        sequence: 2,
        schema_version: 2,
        task_id: 'task-a',
        step_id: 'compress-degrade',
        agent_id: null,
        parent_id: null,
        tool_call_id: null,
        approval_id: null,
        resource_job_id: null,
        correlation_id: null,
        event_type: 'context.compress.degraded',
        payload: { outcome: 'degraded', failure_code: 'adaptive_compress_error' },
        created_at: '2026-09-06T00:00:01Z',
      }),
      TaskEventSchema.parse({
        sequence: 3,
        schema_version: 2,
        task_id: 'task-a',
        step_id: 'compress-halt',
        agent_id: null,
        parent_id: null,
        tool_call_id: null,
        approval_id: null,
        resource_job_id: null,
        correlation_id: null,
        event_type: 'context.compress.halted',
        payload: { outcome: 'halted', failure_code: 'still_over_limit' },
        created_at: '2026-09-06T00:00:02Z',
      }),
    ];

    const projection = projectTaskExecution(taskA, events);
    expect(projection.checklist.map((item) => item.status)).toEqual([
      'completed',
      'degraded',
      'failed',
    ]);
  });
});
