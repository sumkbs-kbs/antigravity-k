import { mkdir } from 'node:fs/promises';
import path from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { z } from 'zod';

const artifactDirectory = process.env.VISUAL_ARTIFACT_DIR
  ?? path.join(process.cwd(), 'test-results', 'task-execution-visual');
const TaskSubmitBodySchema = z.object({ prompt: z.string() });
const ApprovalDecisionBodySchema = z.object({ decision: z.string() });

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

const pendingApproval = {
  request_id: 'approval-ui',
  tool_name: 'apply_patch',
  risk_level: 'high',
  description: '설정 파일 수정',
  diff_preview: '--- a/settings.ts\n+++ b/settings.ts\n@@ -1 +1 @@\n-old\n+new',
  status: 'pending',
  created_at: 1_777_000_000,
  timeout_sec: 120,
  auto_review: null,
};

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
      body: JSON.stringify({ task_id: 'task-ui', events, last_sequence: 5, has_more: false }),
    });
  });
  await page.route(/\/api\/tasks\/task-ui\/events\/stream(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: stream.end\ndata: {"task_id":"task-ui","last_sequence":5,"status":"done"}\n\n',
    });
  });
  await page.route(/\/api\/approval\/pending(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ pending: [pendingApproval], count: 1 }) });
  });
  await page.route(/\/api\/system\/metrics(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, memory_mb: 512, cpu_percent: 8, total_tokens: 2048 }) });
  });
}

test.beforeEach(async ({ page }) => {
  await installAuthenticatedSession(page);
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

    const prompt = page.getByLabel('새 작업 지시');
    await prompt.focus();
    await expect(prompt).toBeFocused();

    const accessibility = await new AxeBuilder({ page }).include('.task-execution-shell').analyze();
    expect(accessibility.violations).toEqual([]);

    const approveButton = page.getByRole('button', { name: '설정 파일 수정 승인' });
    await approveButton.hover();
    await expect(approveButton).toHaveCSS('background-color', 'rgb(91, 75, 196)');

    await page.addStyleTag({
      content: `
        html, body, #root, .app-layout, .main-content {
          height: auto !important;
          overflow: visible !important;
        }
        .agent-page {
          overflow: visible !important;
        }
        [data-react-grab-toolbar] {
          display: none !important;
        }
      `,
    });
    await page.locator('[data-react-grab-toolbar]').evaluateAll((nodes) => {
      for (const node of nodes) node.remove();
    });
    await page.locator('.task-execution-shell').screenshot({
      path: path.join(artifactDirectory, `${viewport.name}-${viewport.width}.png`),
    });
  });
}

test('shows a recoverable replay error', async ({ page }) => {
  await installTaskFixtures(page, true);
  await page.goto('/agent');

  await expect(page.getByRole('region', { name: '실행 추적' }).getByRole('alert')).toContainText('503');
  await expect(page.getByRole('button', { name: '다시 연결' })).toBeVisible();
});

test('runs submit, approval, cancel, resume, and reconnect without sequence duplication', async ({ page }) => {
  let taskStatus = 'running';
  let approvalResolved = false;
  let streamAttempts = 0;
  const replayCursors: number[] = [];
  const submittedPrompts: string[] = [];
  const decisions: string[] = [];

  await page.route(/\/api\/tasks(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        data: [{ ...tasks.data[0], status: taskStatus }],
      }),
    });
  });
  await page.route(/\/api\/tasks\/submit$/, async (route) => {
    const body = TaskSubmitBodySchema.parse(route.request().postDataJSON());
    submittedPrompts.push(body.prompt);
    await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ status: 'submitted', task_id: 'task-ui' }) });
  });
  await page.route(/\/api\/tasks\/task-ui\/cancel$/, async (route) => {
    taskStatus = 'cancelled';
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'cancelled', task_id: 'task-ui' }) });
  });
  await page.route(/\/api\/tasks\/task-ui\/resume$/, async (route) => {
    taskStatus = 'running';
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'resumed', task_id: 'task-ui' }) });
  });
  await page.route(/\/api\/tasks\/task-ui\/events(?:\?.*)?$/, async (route) => {
    const cursor = Number(new URL(route.request().url()).searchParams.get('after_sequence') ?? '0');
    replayCursors.push(cursor);
    const replayEvents = cursor === 0
      ? events.slice(0, 3)
      : events.filter((item) => Number(item.sequence) > cursor);
    const lastSequence = Number(replayEvents.at(-1)?.sequence ?? cursor);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        task_id: 'task-ui',
        events: replayEvents,
        last_sequence: lastSequence,
        has_more: lastSequence < 5,
      }),
    });
  });
  await page.route(/\/api\/tasks\/task-ui\/events\/stream(?:\?.*)?$/, async (route) => {
    streamAttempts += 1;
    if (streamAttempts === 1) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'temporary disconnect' }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: stream.end\ndata: {"task_id":"task-ui","last_sequence":5,"status":"done"}\n\n',
    });
  });
  await page.route(/\/api\/approval\/pending(?:\?.*)?$/, async (route) => {
    const pending = approvalResolved ? [] : [pendingApproval];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ pending, count: pending.length }) });
  });
  await page.route(/\/api\/approval\/approval-ui\/resolve$/, async (route) => {
    const body = ApprovalDecisionBodySchema.parse(route.request().postDataJSON());
    decisions.push(body.decision);
    approvalResolved = true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, request_id: 'approval-ui', status: 'approved' }) });
  });
  await page.route(/\/api\/system\/metrics(?:\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, memory_mb: 512, cpu_percent: 8, total_tokens: 2048 }) });
  });

  await page.goto('/agent');
  await expect(page.getByRole('heading', { name: '승인 대기열' })).toBeVisible();
  await expect(page.getByRole('button', { name: '설정 파일 수정 apply_patch · high' })).toBeVisible();
  await expect.poll(() => replayCursors.includes(5), { timeout: 5_000 }).toBe(true);

  await page.getByLabel('새 작업 지시').fill('  브라우저 lifecycle 검증  ');
  await page.getByRole('button', { name: '작업 제출' }).click();
  await expect.poll(() => submittedPrompts).toEqual(['브라우저 lifecycle 검증']);

  await page.getByRole('button', { name: '설정 파일 수정 승인' }).click();
  await expect.poll(() => decisions).toEqual(['approve']);
  await expect(page.getByText('대기 중인 승인 요청이 없습니다.')).toBeVisible();

  await page.getByRole('button', { name: '병렬 에이전트로 dashboard 검증 취소' }).click();
  await expect(page.getByRole('button', { name: '병렬 에이전트로 dashboard 검증 재개' })).toBeVisible();
  await page.getByRole('button', { name: '병렬 에이전트로 dashboard 검증 재개' }).click();
  await expect(page.getByRole('button', { name: '병렬 에이전트로 dashboard 검증 취소' })).toBeVisible();

  await expect(page.getByText('스트림 완료')).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText('5 events')).toBeVisible();
  expect(streamAttempts).toBeGreaterThanOrEqual(2);
  expect(replayCursors).toContain(3);
  expect(replayCursors).toContain(5);
  const accessibility = await new AxeBuilder({ page }).include('.task-execution-shell').analyze();
  expect(accessibility.violations).toEqual([]);
});

test('repairs a live stream gap with authoritative replay before completing', async ({ page }) => {
  const replayCursors: number[] = [];

  // Given: the initial replay ends at sequence 2 and the live stream jumps to sequence 4.
  await installTaskFixtures(page);
  await page.route(/\/api\/tasks\/task-ui\/events(?:\?.*)?$/, async (route) => {
    const cursor = Number(new URL(route.request().url()).searchParams.get('after_sequence') ?? '0');
    replayCursors.push(cursor);
    const replayEvents = cursor === 0 ? events.slice(0, 2) : events.slice(2, 4);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ task_id: 'task-ui', events: replayEvents, last_sequence: cursor === 0 ? 2 : 4, has_more: false }),
    });
  });
  await page.route(/\/api\/tasks\/task-ui\/events\/stream(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        `id: 4\nevent: tool.completed\ndata: ${JSON.stringify(events[3])}`,
        'event: stream.end\ndata: {"task_id":"task-ui","last_sequence":4,"status":"done"}',
        '',
      ].join('\n\n'),
    });
  });

  // When: the dashboard consumes the replay and the out-of-order live event.
  await page.goto('/agent');

  // Then: it replays the missing range and renders each event exactly once.
  await expect(page.getByText('4 events')).toBeVisible({ timeout: 5_000 });
  expect(replayCursors).toEqual([0, 2]);
  await expect(page.getByText('스트림 완료')).toBeVisible();
});

test('does not mark an incomplete terminal replay as complete', async ({ page }) => {
  const replayCursors: number[] = [];

  // Given: the server reports a terminal cursor that the replay cannot make contiguous.
  await installTaskFixtures(page);
  await page.route(/\/api\/tasks\/task-ui\/events(?:\?.*)?$/, async (route) => {
    const cursor = Number(new URL(route.request().url()).searchParams.get('after_sequence') ?? '0');
    replayCursors.push(cursor);
    const replayEvents = cursor === 0 ? [events[0], events[2]] : [events[2]];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ task_id: 'task-ui', events: replayEvents, last_sequence: cursor === 0 ? 3 : 4, has_more: false }),
    });
  });
  await page.route(/\/api\/tasks\/task-ui\/events\/stream(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: stream.end\ndata: {"task_id":"task-ui","last_sequence":4,"status":"done"}\n\n',
    });
  });

  // When: the dashboard receives the terminal stream frame.
  await page.goto('/agent');

  // Then: it reports the incomplete replay instead of claiming completion.
  await expect(page.getByRole('region', { name: '실행 추적' }).getByRole('alert')).toContainText('incomplete');
  await expect(page.getByText('연결 오류')).toBeVisible();
  expect(replayCursors).toEqual([0, 1]);
});
