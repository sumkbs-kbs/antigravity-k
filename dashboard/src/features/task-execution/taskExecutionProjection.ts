import type { AgentId, JsonValue, StepId, TaskEvent, TaskId } from './taskExecutionSchema';

export type ExecutionStatus = 'running' | 'completed' | 'failed' | 'cancelled' | 'waiting' | 'degraded' | 'unknown';

export type AgentProjection = Readonly<{
  id: AgentId;
  parentId: AgentId | null;
  label: string;
  role: string | null;
  depth: number;
  status: ExecutionStatus;
  lastSequence: number;
}>;

export type ChecklistProjection = Readonly<{
  id: string;
  label: string;
  status: ExecutionStatus;
  firstSequence: number;
  lastSequence: number;
  agentId: AgentId | null;
}>;

export type TerminalProjection = Readonly<{
  id: string;
  toolName: string;
  command: string | null;
  output: string;
  status: ExecutionStatus;
  firstSequence: number;
  lastSequence: number;
  truncated: boolean;
}>;

export type TaskExecutionProjection = Readonly<{
  agents: readonly AgentProjection[];
  checklist: readonly ChecklistProjection[];
  terminals: readonly TerminalProjection[];
  lastSequence: number;
}>;

type AgentAccumulator = {
  id: AgentId;
  parentId: AgentId | null;
  label: string;
  role: string | null;
  firstSequence: number;
  lastSequence: number;
  status: ExecutionStatus;
};

type ChecklistAccumulator = {
  id: string;
  label: string;
  status: ExecutionStatus;
  firstSequence: number;
  lastSequence: number;
  agentId: AgentId | null;
};

type TerminalAccumulator = {
  id: string;
  toolName: string;
  command: string | null;
  outputParts: string[];
  status: ExecutionStatus;
  firstSequence: number;
  lastSequence: number;
};

const TERMINAL_OUTPUT_LIMIT = 6_000;

function payloadObject(payload: JsonValue): Readonly<Record<string, JsonValue>> | null {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) return null;
  return payload;
}

function payloadString(payload: JsonValue, keys: readonly string[]): string | null {
  const object = payloadObject(payload);
  if (object === null) return null;
  for (const key of keys) {
    const value = object[key];
    if (typeof value === 'string' && value.trim().length > 0) return value.trim();
  }
  return null;
}

function payloadText(payload: JsonValue, keys: readonly string[]): string | null {
  const object = payloadObject(payload);
  if (object === null) return null;
  const values: string[] = [];
  for (const key of keys) {
    const value = object[key];
    if (typeof value === 'string' && value.length > 0) values.push(value);
    else if (value !== undefined && value !== null && typeof value !== 'string') {
      values.push(JSON.stringify(value, null, 2));
    }
  }
  return values.length > 0 ? values.join('\n') : null;
}

function statusFor(eventType: string): ExecutionStatus {
  const normalized = eventType.toLowerCase();
  // CTX-03: compress outcomes must map to distinct UI states matching server policy.
  if (normalized.includes('compress') && normalized.includes('halt')) return 'failed';
  if (normalized.includes('degrad')) return 'degraded';
  if (normalized.includes('fail') || normalized.includes('error')) return 'failed';
  if (normalized.includes('cancel')) return 'cancelled';
  if (normalized.includes('complete') || normalized.includes('finish') || normalized.includes('success')) {
    return 'completed';
  }
  if (normalized.includes('approval') || normalized.includes('wait') || normalized.includes('block')) {
    return 'waiting';
  }
  if (normalized.includes('start') || normalized.includes('run') || normalized.includes('progress')) return 'running';
  return 'unknown';
}

function displayEventType(eventType: string): string {
  return eventType.replaceAll(/[._:-]+/g, ' ');
}

function isTerminalEvent(event: TaskEvent): boolean {
  if (event.tool_call_id !== null) return true;
  const normalized = event.event_type.toLowerCase();
  return ['tool', 'terminal', 'command', 'shell', 'process', 'approval'].some((part) => normalized.includes(part));
}

export function boundTerminalOutput(output: string, limit = TERMINAL_OUTPUT_LIMIT): string {
  if (output.length <= limit) return output;
  const headLength = Math.ceil(limit / 2);
  const tailLength = Math.floor(limit / 2);
  const omitted = output.length - headLength - tailLength;
  return `${output.slice(0, headLength)}\n\n[${omitted} characters omitted]\n\n${output.slice(-tailLength)}`;
}

function agentDepth(agent: AgentAccumulator, agents: ReadonlyMap<AgentId, AgentAccumulator>): number {
  let depth = 0;
  let parentId = agent.parentId;
  const visited = new Set<AgentId>([agent.id]);
  while (parentId !== null && !visited.has(parentId)) {
    const parent = agents.get(parentId);
    if (parent === undefined) break;
    depth += 1;
    visited.add(parentId);
    parentId = parent.parentId;
  }
  return depth;
}

export function projectTaskExecution(taskId: TaskId, sourceEvents: readonly TaskEvent[]): TaskExecutionProjection {
  const events = sourceEvents
    .filter((event) => event.task_id === taskId)
    .slice()
    .sort((left, right) => left.sequence - right.sequence);
  const agents = new Map<AgentId, AgentAccumulator>();
  const checklist = new Map<StepId, ChecklistAccumulator>();
  const terminals = new Map<string, TerminalAccumulator>();

  for (const event of events) {
    const status = statusFor(event.event_type);
    if (event.agent_id !== null) {
      const existing = agents.get(event.agent_id);
      const label = payloadString(event.payload, ['agent_name', 'name']) ?? event.agent_id;
      const role = payloadString(event.payload, ['role', 'agent_role']);
      if (existing === undefined) {
        agents.set(event.agent_id, {
          id: event.agent_id,
          parentId: event.parent_id,
          label,
          role,
          firstSequence: event.sequence,
          lastSequence: event.sequence,
          status,
        });
      } else {
        existing.parentId = event.parent_id ?? existing.parentId;
        existing.label = label;
        existing.role = role ?? existing.role;
        existing.lastSequence = event.sequence;
        existing.status = status === 'unknown' ? existing.status : status;
      }
    }

    if (event.step_id !== null) {
      const existing = checklist.get(event.step_id);
      const label = payloadString(event.payload, ['title', 'step', 'description', 'name'])
        ?? displayEventType(event.event_type);
      if (existing === undefined) {
        checklist.set(event.step_id, {
          id: event.step_id,
          label,
          status,
          firstSequence: event.sequence,
          lastSequence: event.sequence,
          agentId: event.agent_id,
        });
      } else {
        existing.label = label;
        existing.lastSequence = event.sequence;
        existing.status = status === 'unknown' ? existing.status : status;
        existing.agentId = event.agent_id ?? existing.agentId;
      }
    }

    if (isTerminalEvent(event)) {
      const id = event.tool_call_id ?? `event-${event.sequence}`;
      const existing = terminals.get(id);
      const toolName = payloadString(event.payload, ['tool_name', 'tool', 'name']) ?? 'tool';
      const command = payloadString(event.payload, ['command', 'cmd']);
      const output = payloadText(event.payload, ['stdout', 'stderr', 'output', 'result', 'error']);
      if (existing === undefined) {
        terminals.set(id, {
          id,
          toolName,
          command,
          outputParts: output === null ? [] : [output],
          status,
          firstSequence: event.sequence,
          lastSequence: event.sequence,
        });
      } else {
        existing.toolName = toolName;
        existing.command = existing.command ?? command;
        if (output !== null) existing.outputParts.push(output);
        existing.lastSequence = event.sequence;
        existing.status = status === 'unknown' ? existing.status : status;
      }
    }
  }

  return {
    agents: [...agents.values()]
      .sort((left, right) => left.firstSequence - right.firstSequence)
      .map((agent) => ({
        id: agent.id,
        parentId: agent.parentId,
        label: agent.label,
        role: agent.role,
        depth: agentDepth(agent, agents),
        status: agent.status,
        lastSequence: agent.lastSequence,
      })),
    checklist: [...checklist.values()].sort((left, right) => left.firstSequence - right.firstSequence),
    terminals: [...terminals.values()]
      .sort((left, right) => left.firstSequence - right.firstSequence)
      .map((terminal) => {
        const fullOutput = terminal.outputParts.join('\n');
        return {
          id: terminal.id,
          toolName: terminal.toolName,
          command: terminal.command,
          output: boundTerminalOutput(fullOutput),
          status: terminal.status,
          firstSequence: terminal.firstSequence,
          lastSequence: terminal.lastSequence,
          truncated: fullOutput.length > TERMINAL_OUTPUT_LIMIT,
        };
      }),
    lastSequence: events.at(-1)?.sequence ?? 0,
  };
}
