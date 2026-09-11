import { expect, test, type Page } from '@playwright/test';
import { z } from 'zod';

const CompactRequestSchema = z.object({
  conversation_id: z.string(),
  expected_revision: z.number(),
  project_id: z.string(),
}).passthrough();

const project = {
  id: 'project-compact',
  name: 'Compact project',
  path: '/tmp/compact-project',
  is_active: true,
  tasks: [],
};

const beforeCompaction = {
  snapshot: {
    conversation_id: 'conversation-compact',
    project_id: project.id,
    revision: 3,
    message_count: 4,
    summary: null,
    retained_message_ids: [],
  },
  messages: [
    { id: 'm1', role: 'user', content: 'earlier request', created_at: 1 },
    { id: 'm2', role: 'assistant', content: 'earlier response', created_at: 2 },
    { id: 'm3', role: 'user', content: 'recent request', created_at: 3 },
    { id: 'm4', role: 'assistant', content: 'recent response', created_at: 4 },
  ],
  token_estimate: 120,
};

const afterCompaction = {
  snapshot: {
    conversation_id: 'conversation-compact',
    project_id: project.id,
    revision: 4,
    message_count: 3,
    summary: 'Earlier turns were compacted.',
    retained_message_ids: ['m3', 'm4'],
  },
  messages: [
    { id: 'summary-4', role: 'system', content: 'Earlier turns were compacted.', created_at: 5 },
    { id: 'm3', role: 'user', content: 'recent request', created_at: 3 },
    { id: 'm4', role: 'assistant', content: 'recent response', created_at: 4 },
  ],
  token_estimate: 72,
};

async function seedConversation(page: Page): Promise<void> {
  await page.addInitScript(({ storageKey, payload, path }) => {
    localStorage.setItem('agk_active_project', path);
    localStorage.setItem(storageKey, JSON.stringify(payload));
  }, {
    storageKey: `antigravity_chat_${project.path}`,
    payload: {
      activeSessionId: 'conversation-compact',
      sessions: [{
        id: 'conversation-compact',
        title: 'Compact me',
        updatedAt: '2026-09-11T00:00:00.000Z',
        messages: beforeCompaction.messages,
        conversationRevision: 3,
      }],
    },
    path: project.path,
  });
}

async function installBaseRoutes(page: Page): Promise<void> {
  await page.route('**/api/projects', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, current_project: project, projects: [project] }),
    });
  });
  await page.route('**/api/workspace/context', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        project_name: project.name,
        workspace_path: project.path,
        target: 'local',
        branch: 'main',
      }),
    });
  });
  await page.route('**/api/**', async (route) => {
    if (route.request().url().includes('/api/projects') || route.request().url().includes('/api/workspace/context')) {
      await route.fallback();
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
}

test.describe('RP-09 manual conversation compaction', () => {
  test('compacts the selected conversation and replaces the local projection with refreshed history', async ({ page }) => {
    const compactRequests: Array<z.infer<typeof CompactRequestSchema>> = [];
    let compacted = false;
    await seedConversation(page);
    await installBaseRoutes(page);
    await page.route('**/v1/conversations/conversation-compact?project_id=project-compact', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(compacted ? afterCompaction : beforeCompaction),
      });
    });
    await page.route('**/v1/conversations/compact', async (route) => {
      compacted = true;
      compactRequests.push(CompactRequestSchema.parse(route.request().postDataJSON()));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(afterCompaction.snapshot) });
    });

    await page.goto('/chat');
    const button = page.getByRole('button', { name: '대화 압축: Compact me' });
    await expect(button).toBeEnabled();
    await button.click();

    await expect.poll(() => compactRequests).toEqual([expect.objectContaining({
      conversation_id: 'conversation-compact',
      expected_revision: 3,
      project_id: project.id,
    })]);
    await expect(page.getByRole('status')).toHaveText('대화를 압축했습니다. 서버 r4의 최신 이력을 반영했습니다.');
    await expect(page.getByText('Earlier turns were compacted.')).toBeVisible();
  });

  test('disables the action and announces pending compaction until the server responds', async ({ page }) => {
    let releaseCompaction: (() => void) | undefined;
    const compactRequestStarted = new Promise<void>((resolve) => {
      releaseCompaction = resolve;
    });
    await seedConversation(page);
    await installBaseRoutes(page);
    await page.route('**/v1/conversations/conversation-compact?project_id=project-compact', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(afterCompaction) });
    });
    await page.route('**/v1/conversations/compact', async (route) => {
      await compactRequestStarted;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(afterCompaction.snapshot) });
    });

    await page.goto('/chat');
    const button = page.getByRole('button', { name: '대화 압축: Compact me' });
    await button.click();

    await expect(button).toBeDisabled();
    await expect(button).toHaveAttribute('aria-busy', 'true');
    await expect(page.getByRole('status')).toHaveText('대화를 압축하고 최신 이력을 동기화하는 중입니다.');
    releaseCompaction?.();
    await expect(button).toBeEnabled();
  });

  test('keeps the compact action available after a 409 and announces the refreshed revision', async ({ page }) => {
    await seedConversation(page);
    await installBaseRoutes(page);
    await page.route('**/v1/conversations/conversation-compact?project_id=project-compact', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(afterCompaction) });
    });
    await page.route('**/v1/conversations/compact', async (route) => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: false,
          error: 'stale_conversation_revision',
          detail: 'Another client compacted the conversation.',
          conversation_id: 'conversation-compact',
          expected_revision: 3,
          current_revision: 4,
        }),
      });
    });

    await page.goto('/chat');
    const button = page.getByRole('button', { name: '대화 압축: Compact me' });
    await button.click();

    await expect(page.getByRole('status')).toHaveText('대화 리비전이 충돌했습니다. 서버 r4의 최신 이력을 반영했습니다. 다시 시도해 주세요.');
    await expect(button).toBeEnabled();
    await expect(page.getByText('Earlier turns were compacted.')).toBeVisible();
  });

  test('announces an API failure without discarding the selected conversation', async ({ page }) => {
    await seedConversation(page);
    await installBaseRoutes(page);
    await page.route('**/v1/conversations/conversation-compact?project_id=project-compact', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(beforeCompaction) });
    });
    await page.route('**/v1/conversations/compact', async (route) => {
      await route.fulfill({ status: 500, contentType: 'text/plain', body: 'provider unavailable' });
    });

    await page.goto('/chat');
    const button = page.getByRole('button', { name: '대화 압축: Compact me' });
    await button.click();

    await expect(page.getByRole('status')).toHaveText(/대화 압축에 실패했습니다: Conversation API 500/);
    await expect(button).toBeEnabled();
    await expect(page.getByText('recent request')).toBeVisible();
  });
});
