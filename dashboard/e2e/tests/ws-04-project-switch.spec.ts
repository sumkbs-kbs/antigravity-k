/**
 * WS-04 · dashboard project switch + request identity sync
 * ========================================================
 * Strong component/browser check: UI project label matches chat payload
 * project_id after a B→C switch. Uses route mocks so it is hermetic.
 */

import { expect, test } from '@playwright/test';

test.describe('WS-04 project switch identity', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test('desktop: label and chat payload project_id match after switch', async ({ page }) => {
    const projects = {
      ok: true,
      workspace: '/tmp/beta',
      current_project: {
        id: 'proj_beta',
        name: 'Beta',
        path: '/tmp/beta',
        is_active: true,
        tasks: [],
      },
      projects: [
        { id: 'proj_beta', name: 'Beta', path: '/tmp/beta', is_active: true, tasks: [] },
        { id: 'proj_gamma', name: 'Gamma', path: '/tmp/gamma', is_active: false, tasks: [] },
      ],
    };

    await page.route('**/api/projects', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(projects) });
        return;
      }
      await route.continue();
    });

    await page.route('**/api/projects/switch', async (route) => {
      const body = route.request().postDataJSON() as { project_id?: string };
      expect(body.project_id).toBe('proj_gamma');
      projects.current_project = {
        id: 'proj_gamma',
        name: 'Gamma',
        path: '/tmp/gamma',
        is_active: true,
        tasks: [],
      };
      projects.projects = projects.projects.map((p) => ({
        ...p,
        is_active: p.id === 'proj_gamma',
      }));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          project: projects.current_project,
          workspace: '/tmp/gamma',
          session_active_project: {
            session_id: 'e2e',
            project_id: 'proj_gamma',
            revision: 11,
            bound_at: new Date().toISOString(),
          },
        }),
      });
    });

    await page.route('**/api/workspace/context', async (route) => {
      const active = projects.current_project;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          project_name: active.name,
          workspace_path: active.path,
          target: '로컬',
          branch: 'main',
          projects: projects.projects,
        }),
      });
    });

    let chatPayload: Record<string, unknown> | null = null;
    await page.route('**/v1/chat/completions', async (route) => {
      chatPayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: [
          'data: {"choices":[{"delta":{"content":"ok-from-gamma"}}]}',
          'data: [DONE]',
          '',
        ].join('\n\n'),
      });
    });

    // Soft-fail unrelated APIs
    await page.route('**/api/**', async (route) => {
      if (route.request().url().includes('/api/projects')) return route.fallback();
      if (route.request().url().includes('/api/workspace/context')) return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      });
    });

    await page.goto('/chat');
    await expect(page.getByTestId('active-project-label')).toBeVisible({ timeout: 15_000 });

    // Switch Beta → Gamma via sidebar project row
    await page.getByTitle('Gamma (/tmp/gamma)').click();
    await expect(page.getByTestId('active-project-label')).toHaveText('Gamma', { timeout: 10_000 });
    await expect(page.getByTestId('active-project-label')).toHaveAttribute('data-project-id', 'proj_gamma');

    const textarea = page.locator('textarea#chat-input');
    await textarea.fill('hello from gamma');
    await textarea.press('Enter');

    await expect.poll(() => chatPayload?.project_id ?? null).toBe('proj_gamma');
    expect(chatPayload?.project_revision).toBe(11);
    // Label and payload identity match
    const label = page.getByTestId('active-project-label');
    await expect(label).toHaveText('Gamma');
    await expect(label).toHaveAttribute('data-project-id', String(chatPayload?.project_id));
  });

  test('mobile viewport: label and payload still match', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const projects = {
      ok: true,
      workspace: '/tmp/mobile-b',
      current_project: {
        id: 'proj_mobile_b',
        name: 'MobileB',
        path: '/tmp/mobile-b',
        is_active: true,
        tasks: [],
      },
      projects: [
        { id: 'proj_mobile_b', name: 'MobileB', path: '/tmp/mobile-b', is_active: true, tasks: [] },
        { id: 'proj_mobile_c', name: 'MobileC', path: '/tmp/mobile-c', is_active: false, tasks: [] },
      ],
    };

    await page.route('**/api/projects', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(projects) });
        return;
      }
      await route.continue();
    });

    await page.route('**/api/projects/switch', async (route) => {
      const body = route.request().postDataJSON() as { project_id?: string };
      expect(body.project_id).toBe('proj_mobile_c');
      projects.current_project = {
        id: 'proj_mobile_c',
        name: 'MobileC',
        path: '/tmp/mobile-c',
        is_active: true,
        tasks: [],
      };
      projects.projects = projects.projects.map((p) => ({
        ...p,
        is_active: p.id === 'proj_mobile_c',
      }));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          project: projects.current_project,
          workspace: '/tmp/mobile-c',
          session_active_project: {
            session_id: 'e2e-mobile',
            project_id: 'proj_mobile_c',
            revision: 7,
            bound_at: new Date().toISOString(),
          },
        }),
      });
    });

    await page.route('**/api/workspace/context', async (route) => {
      const active = projects.current_project;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          project_name: active.name,
          workspace_path: active.path,
          target: '로컬',
          branch: 'main',
          projects: projects.projects,
        }),
      });
    });

    let chatPayload: Record<string, unknown> | null = null;
    await page.route('**/v1/chat/completions', async (route) => {
      chatPayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"choices":[{"delta":{"content":"m"}}]}\n\ndata: [DONE]\n\n',
      });
    });

    await page.route('**/api/**', async (route) => {
      if (route.request().url().includes('/api/projects')) return route.fallback();
      if (route.request().url().includes('/api/workspace/context')) return route.fallback();
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
    });

    await page.goto('/chat');
    await expect(page.getByTestId('active-project-label')).toBeVisible({ timeout: 15_000 });

    // Real hydrate/switch path (same as desktop): B → C via sidebar row
    await page.getByTitle('MobileC (/tmp/mobile-c)').click();
    await expect(page.getByTestId('active-project-label')).toHaveText('MobileC', { timeout: 10_000 });
    await expect(page.getByTestId('active-project-label')).toHaveAttribute('data-project-id', 'proj_mobile_c');

    const textarea = page.locator('textarea#chat-input');
    await textarea.fill('mobile ping');
    await textarea.press('Enter');

    // Hard-fail: project_id must be present and match label
    await expect.poll(() => chatPayload?.project_id ?? null).toBe('proj_mobile_c');
    expect(chatPayload?.project_id).toBe('proj_mobile_c');
    expect(chatPayload?.project_revision).toBe(7);
    const label = page.getByTestId('active-project-label');
    await expect(label).toHaveText('MobileC');
    await expect(label).toHaveAttribute('data-project-id', String(chatPayload?.project_id));
  });

});
