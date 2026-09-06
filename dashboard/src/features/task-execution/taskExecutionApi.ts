import ky from 'ky';

import { createAccessPinHeaders } from '../../utils/accessPinCredential';
import {
  createProjectIdentityHeaders,
  withProjectIdentityPayload,
} from '../../api/projectIdentity';

import {
  TaskEventSchema,
  TaskActionResponseSchema,
  TaskEventsResponseSchema,
  TaskForkResponseSchema,
  TaskListResponseSchema,
  TaskSubmitResponseSchema,
  TaskStreamEndSchema,
  type TaskEvent,
  type TaskId,
  type TaskSummary,
} from './taskExecutionSchema';

export type SseFrame = Readonly<{
  id: string | null;
  event: string | null;
  data: string;
}>;

export type ParsedSseChunk = Readonly<{
  frames: readonly SseFrame[];
  remainder: string;
}>;

export type TaskStreamResult = Readonly<{
  status: string;
  lastSequence: number;
}>;

type TaskStreamHandlers = Readonly<{
  onEvent: (event: TaskEvent) => void;
}>;

export class TaskEventStreamError extends Error {
  readonly code: 'missing-body' | 'invalid-event';

  constructor(code: 'missing-body' | 'invalid-event', message: string) {
    super(message);
    this.name = 'TaskEventStreamError';
    this.code = code;
  }
}

function accessHeaders(accept = 'application/json'): Headers {
  return createProjectIdentityHeaders({ Accept: accept });
}

export function parseSseChunk(input: string): ParsedSseChunk {
  const normalized = input.replaceAll('\r\n', '\n');
  const segments = normalized.split('\n\n');
  const remainder = segments.pop() ?? '';
  const frames: SseFrame[] = [];

  for (const segment of segments) {
    let id: string | null = null;
    let event: string | null = null;
    const data: string[] = [];
    for (const line of segment.split('\n')) {
      if (line.startsWith(':')) continue;
      const separator = line.indexOf(':');
      const field = separator < 0 ? line : line.slice(0, separator);
      const rawValue = separator < 0 ? '' : line.slice(separator + 1);
      const value = rawValue.startsWith(' ') ? rawValue.slice(1) : rawValue;
      if (field === 'id') id = value;
      else if (field === 'event') event = value;
      else if (field === 'data') data.push(value);
    }
    if (data.length > 0) frames.push({ id, event, data: data.join('\n') });
  }

  return { frames, remainder };
}

export async function fetchTaskList(signal: AbortSignal): Promise<readonly TaskSummary[]> {
  const raw: unknown = await ky.get('/api/tasks', {
    headers: accessHeaders(),
    signal,
    retry: 1,
    timeout: 10_000,
  }).json();
  return TaskListResponseSchema.parse(raw).data;
}

export async function submitTask(prompt: string): Promise<TaskId> {
  const raw: unknown = await ky.post('/api/tasks/submit', {
    headers: accessHeaders(),
    json: withProjectIdentityPayload({ prompt }),
    retry: 0,
    timeout: 10_000,
  }).json();
  return TaskSubmitResponseSchema.parse(raw).task_id;
}

export async function forkTask(taskId: TaskId): Promise<TaskId> {
  const raw: unknown = await ky.post(`/api/tasks/${encodeURIComponent(taskId)}/fork`, {
    headers: accessHeaders(),
    json: {},
    retry: 0,
    timeout: 10_000,
  }).json();
  return TaskForkResponseSchema.parse(raw).task_id;
}

async function performTaskAction(taskId: TaskId, action: 'cancel' | 'resume'): Promise<void> {
  const raw: unknown = await ky.post(`/api/tasks/${encodeURIComponent(taskId)}/${action}`, {
    headers: accessHeaders(),
    retry: 0,
    timeout: 10_000,
  }).json();
  TaskActionResponseSchema.parse(raw);
}

export async function cancelTask(taskId: TaskId): Promise<void> {
  await performTaskAction(taskId, 'cancel');
}

export async function resumeTask(taskId: TaskId): Promise<void> {
  await performTaskAction(taskId, 'resume');
}

export async function fetchTaskEvents(
  taskId: TaskId,
  afterSequence: number,
  signal: AbortSignal,
): Promise<Readonly<{ events: readonly TaskEvent[]; lastSequence: number }>> {
  const events: TaskEvent[] = [];
  let sequence = afterSequence;

  while (true) {
    const raw: unknown = await ky.get(`/api/tasks/${encodeURIComponent(taskId)}/events`, {
      headers: accessHeaders(),
      searchParams: { after_sequence: sequence, limit: 500 },
      signal,
      retry: 1,
      timeout: 10_000,
    }).json();
    const response = TaskEventsResponseSchema.parse(raw);
    events.push(...response.events);
    if (!response.has_more) {
      return { events, lastSequence: response.last_sequence };
    }
    if (response.last_sequence <= sequence) {
      throw new TaskEventStreamError('invalid-event', 'Task event replay cursor did not advance.');
    }
    sequence = response.last_sequence;
  }
}

function frameResult(frame: SseFrame): TaskStreamResult | TaskEvent {
  const raw: unknown = JSON.parse(frame.data);
  if (frame.event === 'stream.end') {
    const end = TaskStreamEndSchema.parse(raw);
    return { status: end.status, lastSequence: end.last_sequence };
  }
  return TaskEventSchema.parse(raw);
}

export async function streamTaskEvents(
  taskId: TaskId,
  afterSequence: number,
  signal: AbortSignal,
  handlers: TaskStreamHandlers,
): Promise<TaskStreamResult> {
  const response = await ky.get(`/api/tasks/${encodeURIComponent(taskId)}/events/stream`, {
    headers: accessHeaders('text/event-stream'),
    searchParams: { after_sequence: afterSequence },
    signal,
    retry: 0,
    timeout: false,
  });
  if (response.body === null) {
    throw new TaskEventStreamError('missing-body', 'Task event stream returned no response body.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.remainder;
    for (const frame of parsed.frames) {
      const item = frameResult(frame);
      if ('status' in item && 'lastSequence' in item) return item;
      handlers.onEvent(item);
    }
  }

  throw new TaskEventStreamError('invalid-event', 'Task event stream ended without a terminal frame.');
}
