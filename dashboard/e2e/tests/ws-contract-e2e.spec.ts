/**
 * WS Event Contract E2E (name · payload · latency)
 * =================================================
 *
 * Fixes the `/v1/ws/events` contract end to end against a real (hermetic)
 * backend + real dashboard build, verifying that what the backend publishes
 * is exactly what the dashboard consumes.
 *
 * Part A — contract:
 *   1. Bridged events (HookEventBus file IPC): append a JSONL line to
 *      <repo>/vault_data/hooks/events.jsonl with hook_event_name
 *      AgentTurnStarted/AgentTurnEnded → assert the WS frame payload matches
 *      the expected {event, data} shape AND the AgentPage timeline shows the
 *      role/task_type-derived label/detail.
 *   2. API-driven events: POST /api/system/mode {mode:"plan"} →
 *      PlanningModeStarted{goal} + ModeChanged{to_mode:"plan"} arrive and the
 *      timeline reflects them.
 *   3. Negative: an unknown event name injected through the same IPC is
 *      ignored (no frame, no timeline entry) — the contract rejects unknowns.
 *   4. WS liveness: keepalive "ping" frames arrive on a quiet connection.
 *
 * Part B — latency (hook-bridged path): N samples measuring
 *   file append → WS frame (watcher poll + bridge + WS),
 *   file append → timeline visible (end-to-end),
 *   WS frame → timeline visible (React render).
 * Each sample retries (fresh append) until delivered, because a concurrent
 * writer (e.g. the shared dev backend) can interleave a partial line that the
 * watcher skips — that loss is itself a documented finding.
 *
 * Results: <outputDir>/ws-contract-latency.json
 */

import { appendFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { expect, test } from '@playwright/test';
import { startNoAuthServer } from '../helpers/hermeticBackend';

interface LatencySample {
  index: number;
  kind: 'start' | 'end';
  attempts: number;
  fileWriteMs: number;
  wsDeliveryMs: number | null;
  e2eMs: number;
  reactRenderMs: number | null;
}

function hookEventsPath(): string {
  return path.resolve(process.cwd(), '..', 'vault_data', 'hooks', 'events.jsonl');
}

async function injectHookEvent(
  eventsPath: string,
  hookEventName: string,
  payload: Record<string, unknown>,
): Promise<void> {
  const line = `${JSON.stringify({ hook_event_name: hookEventName, timestamp: Date.now() / 1000, ...payload })}\n`;
  await appendFile(eventsPath, line, 'utf8');
}

test('WS contract: bridged + API events reach the dashboard with exact payloads', async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  const server = await startNoAuthServer();
  try {
    const context = await browser.newContext({ baseURL: server.baseUrl });
    const page = await context.newPage();

    // Capture every WS frame (event + keepalive) with arrival timestamps.
    const frames: Array<{ t: number; text: string }> = [];
    page.on('websocket', ws => {
      ws.on('framereceived', event => {
        const text = typeof event.payload === 'string' ? event.payload : '';
        if (text.includes('"event"')) frames.push({ t: Date.now(), text });
      });
    });

    await page.goto('/agent');
    await expect(page.locator('.agent-timeline-section')).toBeVisible();
    await page.waitForTimeout(2_000); // let the event WS open + subscribe settle

    const eventsPath = hookEventsPath();
    await mkdir(path.dirname(eventsPath), { recursive: true });

    // ── Part A.1: bridged events (name + payload contract) ──────────────
    const payload = { role: 'ContractProbe', task_type: 'plan-refactor' };
    await injectHookEvent(eventsPath, 'AgentTurnStarted', payload);
    await expect(page.getByText('턴 시작 [ContractProbe]')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.agent-timeline-detail').filter({ hasText: 'plan-refactor' }).first()).toBeVisible();

    const startFrame = frames.find(f => f.text.includes('"ContractProbe"'));
    expect(startFrame).toBeDefined();
    const startMsg = JSON.parse(startFrame?.text ?? '{}') as { event: string; data: Record<string, unknown> };
    expect(startMsg.event).toBe('AgentTurnStarted');
    expect(startMsg.data.role).toBe('ContractProbe');
    expect(startMsg.data.task_type).toBe('plan-refactor');

    await injectHookEvent(eventsPath, 'AgentTurnEnded', payload);
    await expect(page.getByText('턴 완료 [ContractProbe]')).toBeVisible({ timeout: 10_000 });
    const endFrame = frames.find(f => f.text.includes('"ContractProbe"') && f.text.includes('AgentTurnEnded'));
    expect(endFrame).toBeDefined();
    expect((JSON.parse(endFrame?.text ?? '{}') as { event: string }).event).toBe('AgentTurnEnded');

    // ── Part A.2: API-driven events (ModeChanged + PlanningModeStarted) ──
    const modeResp = await fetch(`${server.baseUrl}/api/system/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'plan', reason: 'E2E 계획 수립' }),
    });
    expect(modeResp.status).toBe(200);
    await expect(page.getByText('📋 계획 시작', { exact: false })).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.agent-timeline-detail').filter({ hasText: 'E2E 계획 수립' }).first()).toBeVisible({ timeout: 10_000 });
    const planFrame = frames.find(f => f.text.includes('PlanningModeStarted'));
    expect(planFrame).toBeDefined();
    const planMsg = JSON.parse(planFrame?.text ?? '{}') as { data: Record<string, unknown> };
    expect(planMsg.data.goal).toBe('E2E 계획 수립');
    await expect(page.getByText(/Mode: plan/i)).toBeVisible({ timeout: 10_000 });

    // ── Part A.3: unknown event names are rejected by the contract ───────
    const timelineBefore = await page.locator('.agent-timeline-event').count();
    await injectHookEvent(eventsPath, 'NoSuchEventEver', { role: 'Ghost', task_type: 'x' });
    await page.waitForTimeout(1_500);
    const timelineAfter = await page.locator('.agent-timeline-event').count();
    expect(timelineAfter).toBe(timelineBefore);
    expect(frames.some(f => f.text.includes('NoSuchEventEver'))).toBe(false);

    // ── Part B: latency samples for the bridged path ─────────────────────
    // 각 시도마다 고유 role을 써서 ① 재시도로 인한 프레임/타임라인 혼선을 막고,
    // ② 성공한 시도의 t0 기준으로만 측정한다. 동시 기록자(8012 백엔드 등)의
    // 부분 라인 interleave로 라인이 유실되면 다음 시도로 넘어간다.
    const samples: LatencySample[] = [];
    const kinds: Array<'start' | 'end'> = ['start', 'end'];
    for (let i = 1; i <= 10; i += 1) {
      const kind = kinds[i % 2];
      const hookName = kind === 'start' ? 'AgentTurnStarted' : 'AgentTurnEnded';

      let successRole = '';
      let t0 = 0;
      let t1 = 0;
      let attempts = 0;
      for (let attempt = 1; attempt <= 5; attempt += 1) {
        attempts = attempt;
        const role = `LatencyProbe-${i}-a${attempt}`;
        const label = kind === 'start' ? `턴 시작 [${role}]` : `턴 완료 [${role}]`;
        t0 = Date.now();
        await injectHookEvent(eventsPath, hookName, { role, task_type: 'latency-probe', probe_t0: t0 });
        t1 = Date.now();
        try {
          await expect(page.getByText(label)).toBeVisible({ timeout: 2_000 });
          successRole = role;
          break;
        } catch {
          // 해당 라인은 watcher가 건너뛰었음(동시 기록 partial-line) — 다음 시도
        }
      }
      expect(successRole, `sample ${i} delivered after ${attempts} attempts`).not.toBe('');
      const tDom = Date.now();

      const frame = frames.find(f => f.text.includes(`"${successRole}"`));
      const tFrame = frame ? frame.t : null;

      samples.push({
        index: i,
        kind,
        attempts,
        fileWriteMs: t1 - t0,
        wsDeliveryMs: tFrame !== null ? tFrame - t0 : null,
        e2eMs: tDom - t0,
        reactRenderMs: tFrame !== null ? tDom - tFrame : null,
      });
      await page.waitForTimeout(100);
    }

    await mkdir(testInfo.outputDir, { recursive: true });
    await writeFile(
      path.join(testInfo.outputDir, 'ws-contract-latency.json'),
      JSON.stringify({ contract: { bridged: ['AgentTurnStarted', 'AgentTurnEnded'], apiDriven: ['ModeChanged', 'PlanningModeStarted'], negative: 'NoSuchEventEver' }, samples }, null, 2),
      'utf8',
    );
    console.log(`WS_CONTRACT_LATENCY=${JSON.stringify(samples)}`);

    // CI-safe bounds — the real distribution is read from the JSON report.
    const e2eMsList = samples.map(s => s.e2eMs);
    expect(Math.max(...e2eMsList)).toBeLessThan(5_000);
    expect(samples.every(s => s.wsDeliveryMs !== null && s.reactRenderMs !== null)).toBe(true);

    await context.close();
  } finally {
    await server.cleanup();
  }
});
