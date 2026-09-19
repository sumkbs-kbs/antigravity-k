import ky, { HTTPError } from 'ky';
import { z } from 'zod';

import { createAccessPinHeaders } from '../../utils/accessPinCredential';

const ObjectiveSchema = z.object({
  objective_id: z.string().min(1),
  project_id: z.string().min(1),
  title: z.string(),
  description: z.string(),
  priority: z.number().int(),
  status: z.enum(['pending', 'claimed', 'done', 'cancelled']),
  trajectory_id: z.string().min(1),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

const SchedulerSchema = z.object({
  should_wake: z.boolean(),
  reason: z.string(),
  delay_seconds: z.number().int().nonnegative(),
  objective_id: z.string().nullable(),
}).passthrough();

const AgencyStatusSchema = z.object({
  project_id: z.string().min(1),
  enabled: z.boolean(),
  paused: z.boolean(),
  scheduler: SchedulerSchema,
  context_text: z.string(),
  context_event_ids: z.array(z.number().int()),
  objective_task_ids: z.array(z.string()),
}).passthrough();

const PauseResponseSchema = z.object({
  project_id: z.string().min(1),
  paused: z.boolean(),
}).passthrough();

export type AgencyObjective = z.infer<typeof ObjectiveSchema>;
export type AgencyStatus = z.infer<typeof AgencyStatusSchema>;

function accessHeaders(): Headers {
  return createAccessPinHeaders({ Accept: 'application/json' });
}

async function agencyJson<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (reason) {
    if (reason instanceof HTTPError && reason.response.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('agk:pin-required'));
    }
    throw reason;
  }
}

export async function fetchAgencyStatus(signal?: AbortSignal, query = ''): Promise<AgencyStatus> {
  const raw: unknown = await agencyJson(ky.get('/api/agency/status', {
    headers: accessHeaders(),
    searchParams: query ? { query } : undefined,
    signal,
    retry: 1,
    timeout: 10_000,
  }).json<unknown>());
  return AgencyStatusSchema.parse(raw);
}

export async function fetchAgencyObjectives(signal?: AbortSignal): Promise<readonly AgencyObjective[]> {
  const raw: unknown = await agencyJson(ky.get('/api/agency/objectives', {
    headers: accessHeaders(),
    signal,
    retry: 1,
    timeout: 10_000,
  }).json<unknown>());
  return z.array(ObjectiveSchema).parse(raw);
}

export async function createAgencyObjective(title: string, description: string, priority: number): Promise<AgencyObjective> {
  const raw: unknown = await agencyJson(ky.post('/api/agency/objectives', {
    headers: accessHeaders(),
    json: { title, description, priority },
    retry: 0,
    timeout: 10_000,
  }).json<unknown>());
  return ObjectiveSchema.parse(raw);
}

async function setAgencyPaused(paused: boolean): Promise<Readonly<{ project_id: string; paused: boolean }>> {
  const raw: unknown = await agencyJson(ky.post(`/api/agency/${paused ? 'pause' : 'resume'}`, {
    headers: accessHeaders(),
    json: {},
    retry: 0,
    timeout: 10_000,
  }).json<unknown>());
  return PauseResponseSchema.parse(raw);
}

export function pauseAgency(): Promise<Readonly<{ project_id: string; paused: boolean }>> {
  return setAgencyPaused(true);
}

export function resumeAgency(): Promise<Readonly<{ project_id: string; paused: boolean }>> {
  return setAgencyPaused(false);
}
