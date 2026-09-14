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

import { apiRequestPath } from '../api/client';
import { readStoredAccessToken } from './accessPinCredential';

interface WsTicketResponse {
  ticket: string;
  expires_in: number;
}

export async function fetchWsTicket(): Promise<string | null> {
  const token = readStoredAccessToken();
  if (token === null) return null;

  try {
    // F-43: `apiRequest`는 '/v1'을 **앞에 붙인다**(`requestJson(`${API_BASE}${endpoint}`)`).
    // 이 endpoint는 이미 자기 namespace('/api/auth')를 갖고 있으므로 `apiRequest`로 보내면
    // 실효 경로가 '/v1/auth/ws-ticket'이 되어 서버(=`/api/auth/ws-ticket`)에 **없는 경로**가 된다.
    // 실효 경로는 SPA fallback에 걸려 405로 끝나고, 이 함수는 그것을 catch로 삼켜 ticket 없이
    // 연결한다 — 그 결과 PIN이 설정된(protected) 배포에서는 WS가 4401로 거절된다.
    const response = (await apiRequestPath('/api/auth/ws-ticket', {
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
