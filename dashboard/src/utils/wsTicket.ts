/**
 * fetchWsTicket — SEC-03 단기 1회성 WebSocket ticket 발급.
 * =========================================================
 * browser WS 클라이언트는 장기 bearer를 URL/subprotocol에 실을 수 없다
 * (로그·browser history 노출). 대신 인증된 HTTP 세션으로 /api/auth/ws-ticket을
 * 호출해 30초짜리 1회성 ticket을 받아 ?ticket= 로 단 한 번 사용한다.
 *
 * 실패(미인증, 서버 구버전 등) 시 null을 반환한다 — 호출부는 익명
 * open_loopback 서버에서처럼 credential 없이 연결을 시도한다.
 */

import { apiRequest } from '../api/client';
import { readStoredAccessToken } from './accessPinCredential';

interface WsTicketResponse {
  ticket: string;
  expires_in: number;
}

export async function fetchWsTicket(): Promise<string | null> {
  const token = readStoredAccessToken();
  if (token === null) return null;

  try {
    const response = (await apiRequest('/auth/ws-ticket', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })) as Partial<WsTicketResponse>;

    if (typeof response?.ticket === 'string' && response.ticket.length > 0) {
      return response.ticket;
    }
    return null;
  } catch {
    return null;
  }
}
