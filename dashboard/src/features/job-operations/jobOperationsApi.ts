import { z } from 'zod';

import { apiRequestPath } from '../../api/client';

const JobScheduleSchema = z.object({
  kind: z.enum(['once', 'interval', 'cron']),
  run_at: z.coerce.date().nullable(),
  interval_seconds: z.number().int().positive().nullable(),
  cron: z.string().nullable(),
}).passthrough();

const JobExecutionSchema = z.object({
  kind: z.enum(['agent', 'command']),
  command: z.array(z.string()),
}).passthrough();

const JobDeliverySchema = z.object({
  kind: z.enum(['none', 'webhook']),
  target: z.string(),
  secret_env: z.string(),
}).passthrough();

export const ScheduledJobSchema = z.object({
  job_id: z.string().min(1),
  name: z.string().min(1),
  prompt: z.string(),
  model: z.string(),
  context: z.record(z.string(), z.unknown()),
  context_mode: z.enum(['fresh', 'continue']),
  use_worktree: z.boolean(),
  execution: JobExecutionSchema,
  delivery: JobDeliverySchema,
  schedule: JobScheduleSchema,
  status: z.enum(['active', 'paused']),
  created_at: z.coerce.date(),
  updated_at: z.coerce.date(),
  next_run_at: z.coerce.date().nullable(),
  last_run_at: z.coerce.date().nullable(),
}).passthrough();

export const JobRunSchema = z.object({
  run_id: z.string().min(1),
  job_id: z.string().min(1),
  status: z.enum(['submitted', 'running', 'succeeded', 'failed']),
  task_id: z.string().nullable(),
  output: z.string(),
  error: z.string(),
  delivery_status: z.enum(['not_configured', 'pending', 'sent', 'failed']),
  delivery_error: z.string(),
  started_at: z.coerce.date(),
  completed_at: z.coerce.date().nullable(),
}).passthrough();

export const JobHealthSchema = z.object({
  generated_at: z.coerce.date(),
  run_window: z.number().int().positive(),
  active_jobs: z.number().int().nonnegative(),
  paused_jobs: z.number().int().nonnegative(),
  open_runs: z.number().int().nonnegative(),
  completed_runs: z.number().int().nonnegative(),
  succeeded_runs: z.number().int().nonnegative(),
  failed_runs: z.number().int().nonnegative(),
  delivery_failed_runs: z.number().int().nonnegative(),
  stale_runs: z.number().int().nonnegative(),
  success_rate: z.number().min(0).max(1),
  healthy: z.boolean(),
  reasons: z.array(z.string()),
}).passthrough();

export const JobRetryResultSchema = z.object({
  source_run_id: z.string().min(1),
  run: JobRunSchema,
}).passthrough();

export type ScheduledJob = z.infer<typeof ScheduledJobSchema>;
export type JobRun = z.infer<typeof JobRunSchema>;
export type JobHealth = z.infer<typeof JobHealthSchema>;
export type JobRetryResult = z.infer<typeof JobRetryResultSchema>;

export async function fetchJobHealth(): Promise<JobHealth> {
  return JobHealthSchema.parse(await apiRequestPath('/api/jobs/health', { suppressLog: true }));
}

export async function fetchScheduledJobs(): Promise<readonly ScheduledJob[]> {
  return z.array(ScheduledJobSchema).parse(await apiRequestPath('/api/jobs', { suppressLog: true }));
}

export async function fetchJobRuns(jobId: string): Promise<readonly JobRun[]> {
  return z.array(JobRunSchema).parse(await apiRequestPath(`/api/jobs/${encodeURIComponent(jobId)}/runs`, { suppressLog: true }));
}

export async function retryJobRun(jobId: string, runId: string): Promise<JobRetryResult> {
  return JobRetryResultSchema.parse(await apiRequestPath(
    `/api/jobs/${encodeURIComponent(jobId)}/runs/${encodeURIComponent(runId)}/retry`,
    { method: 'POST', suppressLog: true },
  ));
}
