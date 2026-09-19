import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fetchJobHealth,
  fetchJobRuns,
  fetchScheduledJobs,
  retryJobRun,
} from './jobOperationsApi';

const healthPayload = {
  generated_at: '2026-08-27T04:00:00Z',
  run_window: 20,
  active_jobs: 2,
  paused_jobs: 1,
  open_runs: 1,
  completed_runs: 4,
  succeeded_runs: 3,
  failed_runs: 1,
  delivery_failed_runs: 0,
  stale_runs: 0,
  success_rate: 0.75,
  healthy: false,
  reasons: ['failure rate exceeds policy'],
};

const jobPayload = {
  job_id: 'job-1',
  name: 'Nightly benchmark',
  prompt: 'Run the benchmark',
  model: 'qwen3.8',
  context: {},
  context_mode: 'fresh',
  use_worktree: false,
  execution: { kind: 'agent', command: [] },
  delivery: { kind: 'none', target: '', secret_env: '' },
  schedule: { kind: 'interval', run_at: null, interval_seconds: 3600, cron: null },
  status: 'active',
  created_at: '2026-08-26T04:00:00Z',
  updated_at: '2026-08-26T04:00:00Z',
  next_run_at: '2026-08-27T05:00:00Z',
  last_run_at: '2026-08-27T03:00:00Z',
};

const runPayload = {
  run_id: 'run-1',
  job_id: 'job-1',
  status: 'failed',
  task_id: 'task-1',
  output: '',
  error: 'provider unavailable',
  delivery_status: 'not_configured',
  delivery_error: '',
  started_at: '2026-08-27T03:00:00Z',
  completed_at: '2026-08-27T03:01:00Z',
};

describe('job operations API boundary', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('parses the health summary and preserves policy reasons', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(healthPayload), { status: 200 }));

    await expect(fetchJobHealth()).resolves.toMatchObject({
      healthy: false,
      success_rate: 0.75,
      reasons: ['failure rate exceeds policy'],
    });
  });

  it('rejects malformed health data at the trust boundary', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ...healthPayload, healthy: 'false' }), { status: 200 }));

    await expect(fetchJobHealth()).rejects.toBeDefined();
  });

  it('loads jobs and runs through their typed endpoints', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify([jobPayload]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([runPayload]), { status: 200 }));

    await expect(fetchScheduledJobs()).resolves.toHaveLength(1);
    await expect(fetchJobRuns('job-1')).resolves.toMatchObject([{ run_id: 'run-1', status: 'failed' }]);

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/jobs');
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/jobs/job-1/runs');
  });

  it('submits one retry request and parses the new run', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      source_run_id: 'run-1',
      run: { ...runPayload, run_id: 'run-2', status: 'submitted' },
    }), { status: 200 }));

    await expect(retryJobRun('job-1', 'run-1')).resolves.toMatchObject({
      source_run_id: 'run-1',
      run: { run_id: 'run-2', status: 'submitted' },
    });
  });
});
