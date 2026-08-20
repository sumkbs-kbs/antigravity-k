import { mkdir } from 'node:fs/promises';
import path from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const artifactDirectory = process.env.VISUAL_ARTIFACT_DIR
  ?? path.join(process.cwd(), 'test-results', 'task-execution-visual');

const tasks = {
  status: 'ok',
  data: [
    {
      task_id: 'task-ui',
      prompt: '병렬 에이전트로 dashboard 검증',
      status: 'running',
      error: null,
      created_at: '2026-08-20T09:00:00Z',
      updated_at: '2026-08-20T09:00:05Z',
    },
    {
      task_id: 'task-secondary',
      prompt: '두 번째 task 실행 기록',
      status: 'done',
      error: null,
      created_at: '2026-08-20T08:00:00Z',
      updated_at: '2026-08-20T08:00:03Z',
    },
  ],
};

function event(sequence: number, fields: Readonly<Record<string, unknown>>): Readonly<Record<string, unknown>> {
  return {
    sequence,
    schema_version: 2,
    task_id: 'task-ui',
    step_id: null,
    agent_id: null,
    parent_id: null,
    tool_call_id: null,
    approval_id: null,
    resource_job_id: null,
    correlation_id: 'run-ui',
    event_type: 'task.event',
    payload: {},
    created_at: `2026-08-20T09:00:0${sequence}Z`,
    ...fields,
  };
}

const events = [
  event(1, {
    step_id: 'plan', agent_id: 'lead', event_type: 'agent.started',
    payload: { agent_name: 'Lead agent', role: 'orchestrator', title: '변경 계획 확정' },
  }),
  event(2, {
    step_id: 'research', agent_id: 'researcher', parent_id: 'lead', tool_call_id: 'tool-search',
    event_type: 'tool.started',
    payload: { agent_name: 'Research agent', role: 'analysis', title: 'API 계약 조사', tool_name: 'search', command: 'rg task events dashboard/src' },
  }),
  event(3, {
    step_id: 'verify', agent_id: 'qa-agent', parent_id: 'lead', tool_call_id: 'tool-test',
    event_type: 'tool.running',
    payload: { agent_name: 'QA agent', role: 'verification', title: '프론트엔드 검증', tool_name: 'terminal', command: 'npm test && npm run build', stdout: '489 tests passed\nproduction build complete\nresponsive checks queued' },
  }),
  event(4, {
    step_id: 'research', agent_id: 'researcher', parent_id: 'lead', tool_call_id: 'tool-search',
    event_type: 'tool.completed',
    payload: { agent_name: 'Research agent', role: 'analysis', title: 'API 계약 조사', tool_name: 'search', output: 'Versioned replay API verified.' },
  }),
  event(5, {
    step_id: 'verify', agent_id: 'qa-agent', parent_id: 'lead', tool_call_id: 'tool-test',
    event_type: 'tool.completed',
    payload: { agent_name: 'QA agent', role: 'verification', title: '프론트엔드 검증', tool_name: 'terminal', stdout: 'No horizontal overflow detected.' },
  }),
];

async function installTaskFixtures(page: Page, failEvents = false): Promise<void> {
  await page.route(/\/api\/tasks(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(tasks) });
  });
  await page.route(/\/api\/tasks\/task-ui\/events(?:\?.*)?$/, async (route) => {
    if (failEvents) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Replay unavailable' }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ task_id: 'task-ui', events, last_sequence: 5 }),
    });
  });
  await page.route(/\/api\/tasks\/task-ui\/events\/stream(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: stream.end\ndata: {"task_id":"task-ui","last_sequence":5,"status":"done"}\n\n',
    });
  });
  await page.route(/\/api\/system\/metrics(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, memory_mb: 512, cpu_percent: 8, total_tokens: 2048 }) });
  });
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('ag_access_pin', '0000'));
  await mkdir(artifactDirectory, { recursive: true });
});

for (const viewport of [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
]) {
  test(`renders the execution trace at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await installTaskFixtures(page);
    await page.goto('/agent');

    const trace = page.getByRole('heading', { name: '실행 추적' });
    await expect(trace).toBeVisible();
    await expect(page.getByText('Lead agent')).toBeVisible();
    await expect(page.getByText('489 tests passed')).toBeVisible();
    await expect(page.getByText('스트림 완료')).toBeVisible();

    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth,
    }));
    expect(overflow.document).toBeLessThanOrEqual(0);
    expect(overflow.body).toBeLessThanOrEqual(0);

    const selector = page.getByLabel('Task 실행');
    await selector.focus();
    await expect(selector).toBeFocused();

    const accessibility = await new AxeBuilder({ page }).include('.task-execution-shell').analyze();
    expect(accessibility.violations).toEqual([]);

    await page.addStyleTag({
      content: `
        html, body, #root, .app-layout, .main-content {
          height: auto !important;
          overflow: visible !important;
        }
        .agent-page {
          overflow: visible !important;
        }
      `,
    });
    await page.locator('.task-execution-shell').screenshot({
      path: path.join(artifactDirectory, `${viewport.name}-${viewport.width}.png`),
    });
  });
}

test('shows a recoverable replay error', async ({ page }) => {
  await installTaskFixtures(page, true);
  await page.goto('/agent');

  await expect(page.getByRole('alert')).toContainText('503');
  await expect(page.getByRole('button', { name: '다시 연결' })).toBeVisible();
});
