// @vitest-environment jsdom
/**
 * F-43 회귀 — WS ticket 은 **정본 경로**로 나가야 한다.
 *
 * 왜 이 파일이 필요한가
 * =====================
 * `fetchWsTicket` 은 `apiRequest`(= 실효 경로에 '/v1' 접두사를 붙이는 래퍼)를 쓰고 있었고,
 * 그래서 `/v1/auth/ws-ticket` — **서버에 없는 경로** — 로 나갔다. 실패는 `catch { return null }`
 * 로 삼켜졌고, ticket 없이 연결하면 WS 게이트는 `open_loopback` 일 때만 통과하므로
 * **PIN 이 설정된 배포에서는 이벤트 스트림이 4401 로 거절되고 3초마다 재시도**했다.
 *
 * 이 결함이 살아남은 이유는 **이 호출의 URL 을 아무 테스트도 보지 않았기 때문**이다:
 * `useEventWebSocket.test.tsx` 는 `fetchWsTicket` 자체를 mock 한다. 그래서 여기서는
 * **실제 URL**을 고정한다 — 접두사 규칙이 다시 어긋나면 여기서 멈춘다.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchWsTicket } from './wsTicket';

function fetchMockReturning(body: unknown, status = 200) {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(
    JSON.stringify(body),
    { status, headers: { 'Content-Type': 'application/json' } },
  ));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('fetchWsTicket', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it('posts to the canonical /api/auth/ws-ticket path and returns the ticket', async () => {
    // Given
    window.sessionStorage.setItem('ag_access_token', 'event-token');
    const fetchMock = fetchMockReturning({ ticket: 'one-time-ticket', expires_in: 30 });

    // When
    const ticket = await fetchWsTicket();

    // Then — 경로는 전체 경로여야 한다. 래퍼가 '/v1'을 앞에 붙이면 서버에 없는 경로가 된다.
    expect(ticket).toBe('one-time-ticket');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/auth/ws-ticket');
    const init = fetchMock.mock.calls[0]?.[1];
    expect(init?.method).toBe('POST');
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer event-token');
  });

  it('never builds a /v1-prefixed ticket path', async () => {
    // Given
    window.sessionStorage.setItem('ag_access_token', 'event-token');
    const fetchMock = fetchMockReturning({ ticket: 't', expires_in: 30 });

    // When
    await fetchWsTicket();

    // Then — 이 문자열이 다시 나타나면 F-43 이 되돌아온 것이다.
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url.startsWith('/v1/')).toBe(false);
  });

  it('does not call the server when no credential is stored', async () => {
    // Given — 익명(open_loopback) 서버 플로우
    const fetchMock = fetchMockReturning({ ticket: 't', expires_in: 30 });

    // When
    const ticket = await fetchWsTicket();

    // Then
    expect(ticket).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('returns null when the server rejects the ticket request', async () => {
    // Given — 서버가 405/401 로 막는 경우(고침 전 실제 동작이었다)
    window.sessionStorage.setItem('ag_access_token', 'event-token');
    fetchMockReturning({ detail: 'Method Not Allowed' }, 405);

    // When / Then — 삼키는 동작 자체를 고정한다(호출부는 credential 없이 연결한다)
    await expect(fetchWsTicket()).resolves.toBeNull();
  });

  it('returns null when the payload carries no usable ticket', async () => {
    // Given
    window.sessionStorage.setItem('ag_access_token', 'event-token');
    fetchMockReturning({ ticket: '', expires_in: 30 });

    // When / Then
    await expect(fetchWsTicket()).resolves.toBeNull();
  });
});
