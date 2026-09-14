/**
 * C33-6 증인 — PIN 보호 서버에서 ticket 이 `?ticket=` 으로 실려 이벤트 스트림이 사는가.
 *
 * 무엇을 재는가
 * -------------
 * attempt-033 은 F-43 으로 정본 경로(`/api/auth/ws-ticket`)를 고쳤지만 **실 브라우저에서 4401 을
 * 관측하지 않았고**, ticket 이 실제로 실려 연결되는지도 재지 않았다(C33-6). 이 증인은 그 구멍을
 * **제품 경로**로 닫는다:
 *
 *   1) **PIN 보호** hermetic 서버(`startAuthServer` — no-auth / `AGK_SEC_DEV_NO_PIN_ALLOW` 단독 아님)
 *   2) 제품 PIN UI 로그인(`loginAndOpenAgent`)
 *   3) ticket 발급이 **`/api/auth/ws-ticket`** 을 치고( `/v1/auth/ws-ticket` 이 아님) ticket 을 받는다
 *      — page 응답 가로채기(단위 mock 아님)
 *   4) 이벤트 WebSocket URL 에 `ticket=` 이 실리고, 그 소켓이 **닫히지 않은 채** 유지된다(4401 루프 아님)
 *
 * fail-first 이빨(같은 PIN 서버, 결정적):
 *   A) `POST /v1/auth/ws-ticket` 는 ticket 을 주지 않는다(401/404/405 — 정본이 아님)
 *   B) (페이지 Origin 설정 뒤) ticket 없이 `/v1/ws/events` 연결 → close **4401**
 *
 * 재지 않는 것: 실 provider(EX-01) · D-71 · ambient 게이트 신설(이 파일은 hermetic 으로 스스로 띄운다).
 * keepalive ping 은 30초 주기라 **프레임 도착을 연결의 유일한 증거로 쓰지 않는다**(자의 함정 —
 * 첫 판본이 그것으로 거짓 실패했다). Playwright `WebSocket.isClosed()` 로 생존을 잰다.
 *
 * 소유: 이름 규칙 `cr\d+-` → required 게이트 `dashboard-e2e-witnesses`(F-42).
 */

import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { expect, test, type Page, type WebSocket } from '@playwright/test';

import { startAuthServer } from '../helpers/hermeticBackend';
import {
  agentBaseUrl,
  bearerToken,
  loginAndOpenAgent,
  seedOpenedRegistry,
} from '../helpers/taskScreen';

type TicketHit = Readonly<{
  url: string;
  status: number;
  body: string;
}>;

type EventWsHit = Readonly<{
  url: string;
  socket: WebSocket;
}>;

function pathOf(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

function isTicketRequest(url: string): boolean {
  return pathOf(url).includes('/auth/ws-ticket');
}

function isEventStreamWs(url: string): boolean {
  return url.includes('/v1/ws/events');
}

function ticketFromBody(body: string): string {
  try {
    const parsed = JSON.parse(body) as { ticket?: unknown };
    return typeof parsed.ticket === 'string' ? parsed.ticket : '';
  } catch {
    return '';
  }
}

async function attachTicketWatcher(page: Page): Promise<{ hits: TicketHit[] }> {
  const hits: TicketHit[] = [];
  page.on('response', (response) => {
    if (!isTicketRequest(response.url())) return;
    void response
      .text()
      .then((text) => {
        hits.push({ url: response.url(), status: response.status(), body: text.slice(0, 800) });
      })
      .catch(() => {
        hits.push({ url: response.url(), status: response.status(), body: '' });
      });
  });
  return { hits };
}

function attachEventWsWatcher(page: Page): { hits: EventWsHit[] } {
  const hits: EventWsHit[] = [];
  page.on('websocket', (ws) => {
    if (!isEventStreamWs(ws.url())) return;
    hits.push({ url: ws.url(), socket: ws });
  });
  return { hits };
}

test('PIN 보호 서버에서 ticket 이 ?ticket= 으로 실려 이벤트 WS 가 연결된다 (C33-6)', async ({ browser }) => {
  test.setTimeout(180_000);
  const stateDirectory = await mkdtemp(path.join(tmpdir(), 'agk-c33-6-'));
  await seedOpenedRegistry(stateDirectory);
  const server = await startAuthServer(1, {
    stateDirectory,
    workingDirectory: stateDirectory,
    overrides: agentBaseUrl(stateDirectory),
  });
  const context = await browser.newContext({ baseURL: server.baseUrl });
  const page = await context.newPage();
  const violations: string[] = [];

  try {
    // Origin allowlist 는 정확 일치다 — fail-first B 전에 같은 origin 으로 페이지를 연다.
    await page.goto('/');
    await page.waitForTimeout(300);

    // ── fail-first A: 죽은 경로(F-43)는 ticket 을 주지 않는다 ───────────────
    const dead = await page.request.post(`${server.baseUrl}/v1/auth/ws-ticket`, {
      data: {},
      failOnStatusCode: false,
    });
    const deadBody = await dead.text();
    const deadTicket = ticketFromBody(deadBody);
    console.log(`[fail-first A] POST /v1/auth/ws-ticket → ${dead.status()} ticketLen=${deadTicket.length}`);
    // 정본이 아닌 경로: 200+ticket 이면 안 된다. (미들웨어 401 / SPA 405 / 404 모두 "죽은 경로")
    if (dead.status() === 200 && deadTicket.length > 0) {
      violations.push(
        `Vdead 죽은 경로 /v1/auth/ws-ticket 이 ticket 을 발급했다(status=200) — F-43 전제와 모순`,
      );
    }

    // ── fail-first B: ticket 없이 붙으면 PIN 서버는 4401 ────────────────────
    const bareClose = await page.evaluate(async (baseUrl) => {
      const wsUrl = `${baseUrl.replace(/^http/, 'ws')}/v1/ws/events`;
      return await new Promise<{ code: number; reason: string }>((resolve) => {
        const socket = new WebSocket(wsUrl);
        const timer = window.setTimeout(() => {
          try {
            socket.close();
          } catch {
            /* already closed */
          }
          resolve({ code: -1, reason: 'timeout-still-open' });
        }, 8_000);
        socket.onclose = (event) => {
          window.clearTimeout(timer);
          resolve({ code: event.code, reason: event.reason || '' });
        };
        socket.onerror = () => {
          /* close follows */
        };
      });
    }, server.baseUrl);
    console.log(`[fail-first B] ticket 없는 WS close=${JSON.stringify(bareClose)}`);
    if (bareClose.code !== 4401) {
      violations.push(
        `V4401 ticket 없는 연결이 4401 로 거절되지 않는다(code=${bareClose.code} reason=${bareClose.reason})`,
      );
    }

    // ── 제품 경로: 로그인 전 watcher 장착 ───────────────────────────────────
    const ticketWatch = await attachTicketWatcher(page);
    const wsWatch = attachEventWsWatcher(page);

    const readiness = await loginAndOpenAgent(page, server.baseUrl);
    console.log(`[login] projectKnown=${String(readiness.projectKnown)}`);
    if (!readiness.projectKnown) {
      violations.push('V0 화면이 프로젝트를 얻지 못했다 — 로그인/하이드레이션 전제 실패');
    }

    // ticket 발급(본문에 ticket 이 있는 200)까지 기다린다 — 빈 body 레이스는 버린다.
    let ticketHit: TicketHit | undefined;
    for (let tick = 0; tick < 40; tick += 1) {
      ticketHit = ticketWatch.hits.find(
        (h) => pathOf(h.url).includes('/api/auth/ws-ticket')
          && h.status === 200
          && ticketFromBody(h.body).length > 0,
      );
      if (ticketHit) break;
      await page.waitForTimeout(250);
    }
    console.log(`[ticket] hits=${JSON.stringify(ticketWatch.hits.map((h) => ({
      path: pathOf(h.url),
      status: h.status,
      ticketLen: ticketFromBody(h.body).length,
    })))}`);
    if (!ticketHit) {
      violations.push(
        `V1 ticket 발급이 /api/auth/ws-ticket 으로 200+ticket 을 받지 못했다`,
      );
    } else {
      const wrong = ticketWatch.hits.some((h) => pathOf(h.url).includes('/v1/auth/ws-ticket'));
      if (wrong) {
        violations.push('V1b 화면이 /v1/auth/ws-ticket(죽은 경로)로 ticket 을 요청했다');
      }
    }

    // 이벤트 WS URL 에 ticket 이 실렸는가 + 소켓이 열린 채로 유지되는가
    let eventHit: EventWsHit | undefined;
    for (let tick = 0; tick < 40; tick += 1) {
      eventHit = wsWatch.hits.find((h) => {
        try {
          return (new URL(h.url).searchParams.get('ticket') ?? '').length > 0;
        } catch {
          return h.url.includes('ticket=');
        }
      });
      if (eventHit) break;
      await page.waitForTimeout(250);
    }
    console.log(`[ws] urls=${JSON.stringify(wsWatch.hits.map((h) => h.url))}`);
    if (!eventHit) {
      violations.push(`V2 이벤트 WS URL 에 ticket= 이 실린 연결을 관측하지 못했다`);
    } else {
      const ticketParam = new URL(eventHit.url).searchParams.get('ticket') ?? '';
      if (ticketParam.length === 0) {
        violations.push(`V2a 이벤트 WS URL 에 ticket 쿼리가 없다(url=${eventHit.url})`);
      }
      // keepalive 는 30초 — 프레임이 아니라 **소켓 생존**으로 연결을 잰다.
      let stayedOpen = false;
      for (let tick = 0; tick < 20; tick += 1) {
        if (!eventHit.socket.isClosed()) {
          stayedOpen = true;
          break;
        }
        await page.waitForTimeout(250);
      }
      // 재연결 루프면 새 소켓이 ticket 을 들고 또 뜰 수 있다 — 현재 목록 중
      // ticket 있는 소켓이 하나라도 살아 있으면 연결됨으로 본다.
      if (!stayedOpen) {
        stayedOpen = wsWatch.hits.some((h) => {
          const hasTicket = h.url.includes('ticket=');
          return hasTicket && !h.socket.isClosed();
        });
      }
      console.log(`[ws] stayedOpen=${String(stayedOpen)} closed=${String(eventHit.socket.isClosed())}`);
      if (!stayedOpen) {
        violations.push(
          `V2b ticket 이 실린 이벤트 WS 가 바로 닫혔다(url=${eventHit.url}) — 4401 루프 가능`,
        );
      }
    }

    // 세션 토큰이 실제로 있는지(익명 open_loopback 우회가 아님)
    try {
      const token = await bearerToken(page);
      console.log(`[session] bearer length=${token.length}`);
    } catch (caught) {
      violations.push(`V3 화면이 bearer 를 갖고 있지 않다 — ${caught instanceof Error ? caught.message : String(caught)}`);
    }

    // 정본 경로를 서버에 직접 한 번 더 확인(브라우저와 같은 자격)
    try {
      const token = await bearerToken(page);
      const canonical = await page.request.post(`${server.baseUrl}/api/auth/ws-ticket`, {
        headers: { Authorization: `Bearer ${token}` },
        failOnStatusCode: false,
      });
      const body = await canonical.text();
      console.log(`[canonical] POST /api/auth/ws-ticket → ${canonical.status()} ticketLen=${ticketFromBody(body).length}`);
      if (canonical.status() !== 200 || ticketFromBody(body).length === 0) {
        violations.push(`V4 정본 ticket 경로가 200+ticket 이 아니다(status=${canonical.status()})`);
      }
    } catch (caught) {
      violations.push(`V4 정본 ticket 프로브 실패 — ${caught instanceof Error ? caught.message : String(caught)}`);
    }

    for (const violation of violations) console.log(`[VIOLATED] ${violation}`);
    console.log(`[결과] ${violations.length === 0 ? 'OK' : `FAIL — 위반 ${violations.length}건`}`);
    expect(violations, `C33-6 위반 ${violations.length}건`).toEqual([]);
  } finally {
    await context.close();
    await server.cleanup();
    await rm(stateDirectory, { recursive: true, force: true });
  }
});
