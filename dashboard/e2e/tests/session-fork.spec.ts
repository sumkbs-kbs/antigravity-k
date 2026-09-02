import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { z } from 'zod';

const EmptyBodySchema = z.object({}).strict();

const sourceTask = {
  task_id: 'task-source',
  prompt: '원본 세션 작업',
  status: 'done',
  output: 'source output',
  error: null,
  created_at: '2026-08-22T01:00:00Z',
  updated_at: '2026-08-22T01:00:05Z',
  completed_at: '2026-08-22T01:00:05Z',
};

const forkedTask = {
  ...sourceTask,
  task_id: 'task-fork',
  status: 'running',
  output: '',
  created_at: '2026-08-22T02:00:00Z',
  updated_at: '2026-08-22T02:00:01Z',
  completed_at: null,
};

function sessionEvent(taskId: string, title: string): Readonly<Record<string, unknown>> {
  return {
    sequence: 1,
    schema_version: 2,
    task_id: taskId,
    step_id: 'session',
    agent_id: 'lead',
    parent_id: null,
    tool_call_id: null,
    approval_id: null,
    resource_job_id: null,
    correlation_id: `run-${taskId}`,
    event_type: 'agent.started',
    payload: { agent_name: 'Lead agent', title },
    created_at: '2026-08-22T02:00:01Z',
  };
}

async function installAuthenticatedSession(page: Page): Promise<void> {
  await page.addInitScript(() => sessionStorage.setItem('ag_access_token', 'e2e-token'));
  await page.route(/\/api\/session\/info(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, session: { subject: 'e2e' } }),
    });
  });
}

async function installSessionForkFixtures(page: Page): Promise<readonly string[]> {
  let forkCreated = false;
  const forkRequests: string[] = [];

  await page.route(/\/api\/tasks(?:\?.*)?$/, async (route) => {
    const data = forkCreated ? [forkedTask, sourceTask] : [sourceTask];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', data }),
    });
  });
  await page.route(/\/api\/tasks\/task-source\/fork$/, async (route) => {
    EmptyBodySchema.parse(route.request().postDataJSON());
    forkRequests.push(route.request().url());
    forkCreated = true;
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'forked', task_id: 'task-fork', source_task_id: 'task-source' }),
    });
  });
  await page.route(/\/api\/tasks\/(task-source|task-fork)\/events(?:\?.*)?$/, async (route) => {
    const taskId = new URL(route.request().url()).pathname.split('/')[3] ?? '';
    const title = taskId === 'task-source' ? '원본 세션 증거' : '분기 세션 실행';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        task_id: taskId,
        events: [sessionEvent(taskId, title)],
        last_sequence: 1,
        has_more: false,
      }),
    });
  });
  await page.route(/\/api\/tasks\/(task-source|task-fork)\/events\/stream(?:\?.*)?$/, async (route) => {
    const taskId = new URL(route.request().url()).pathname.split('/')[3] ?? '';
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: stream.end\ndata: {"task_id":"${taskId}","last_sequence":1,"status":"done"}\n\n`,
    });
  });
  await page.route(/\/api\/approval\/pending(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ pending: [], count: 0 }) });
  });
  await page.route(/\/api\/system\/metrics(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, memory_mb: 512, cpu_percent: 8, total_tokens: 2048 }) });
  });

  return forkRequests;
}

test('forks a historical session and preserves source replay', async ({ page }) => {
  await installAuthenticatedSession(page);
  const forkRequests = await installSessionForkFixtures(page);
  await page.goto('/agent');

  await expect(page.getByRole('heading', { name: '세션 히스토리' })).toBeVisible();
  await expect(page.getByText('원본 세션 증거')).toBeVisible();
  await page.getByRole('button', { name: '원본 세션 작업 분기' }).click();

  await expect.poll(() => forkRequests.length).toBe(1);
  await expect(page.getByText('2개 세션')).toBeVisible();
  await expect(page.getByRole('button', { name: '원본 세션 작업, 상태 running' })).toBeVisible();
  await expect(page.getByText('분기 세션 실행')).toBeVisible();

  await page.getByRole('button', { name: '원본 세션 작업, 상태 done' }).click();
  await expect(page.getByText('원본 세션 증거')).toBeVisible();
  await expect(page.getByRole('button', { name: '원본 세션 작업, 상태 running' })).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).include('.task-execution-shell').analyze();
  expect(accessibility.violations).toEqual([]);
});
