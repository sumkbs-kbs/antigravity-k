/**
 * NX-09 계약 — 대화 **정체성**은 클라이언트가 만든다.
 *
 * 왜 이 계약이 필요한가(실측 근거 `docs/qa/2026-09-16-followup/nx09/`):
 * 세션이 없는 상태에서 첫 메시지가 들어오면 요청에 `conversation_id` 가 실리지 않고, 서버는
 * 폴백 id(`conv_unspecified`)를 붙인다. 클라이언트가 그 값을 자기 대화 id 로 채택하면
 * (a) 이력 목록에 그 대화가 없고, (b) 서로 다른 창/사용자의 첫 대화가 **한 레코드로 섞이며**,
 * (c) 그 레코드를 지우면 남의 이력도 함께 사라진다.
 */

import { describe, it, expect, beforeEach } from 'vitest';

import { useChatStore, SERVER_FALLBACK_CONVERSATION_ID } from '../chatStore';

describe('NX-09 chatStore 대화 정체성', () => {
  beforeEach(() => {
    window.localStorage.clear();
    useChatStore.setState({
      sessions: [],
      activeSessionId: null,
      activeSession: null,
      messages: [],
      conversationRevision: 0,
    });
  });

  it('세션이 없는 첫 메시지는 세션을 만들고 클라이언트 id 를 갖는다', () => {
    useChatStore.getState().addMessage({ role: 'user', content: '첫 대화입니다' });
    const state = useChatStore.getState();

    expect(state.activeSessionId, '첫 대화는 자기 id 를 가져야 한다').toBeTruthy();
    expect(state.activeSessionId).not.toBe(SERVER_FALLBACK_CONVERSATION_ID);
    expect(state.sessions[0]?.id).toBe(state.activeSessionId);
    expect(state.sessions[0]?.messages).toHaveLength(1);
    // 제목은 첫 사용자 메시지에서 파생된다(기존 동작 유지).
    expect(state.sessions[0]?.title).toContain('첫 대화');
  });

  it('두 번째 대화는 새 id 를 만든다 — 한 레코드로 합쳐지지 않는다', () => {
    useChatStore.getState().addMessage({ role: 'user', content: 'A' });
    const firstId = useChatStore.getState().activeSessionId;

    useChatStore.getState().createNewSession();
    useChatStore.getState().addMessage({ role: 'user', content: 'B' });

    const state = useChatStore.getState();
    expect(state.activeSessionId).not.toBe(firstId);
    expect(state.sessions.map((session) => session.id)).toContain(firstId);
    expect(state.sessions.map((session) => session.id)).toContain(state.activeSessionId);
  });

  it('서버 폴백 id 는 채택하지 않는다 — 현재 대화 id 를 유지한다', () => {
    useChatStore.getState().addMessage({ role: 'user', content: 'C' });
    const ownId = useChatStore.getState().activeSessionId;

    useChatStore.getState().applyServerSnapshot({
      conversation_id: SERVER_FALLBACK_CONVERSATION_ID,
      revision: 1,
      messages: [{ role: 'user', content: 'C' }],
    });

    expect(useChatStore.getState().activeSessionId).toBe(ownId);
    expect(useChatStore.getState().conversationRevision).toBe(1);
  });

  it('서버가 클라이언트 id 를 돌려주면 그것이 권위다(리비전 반영)', () => {
    useChatStore.getState().createNewSession();
    const ownId = useChatStore.getState().activeSessionId ?? '';
    expect(ownId).toBeTruthy();

    useChatStore.getState().applyServerSnapshot({
      conversation_id: ownId,
      revision: 7,
      messages: [
        { role: 'user', content: '질문' },
        { role: 'assistant', content: '답' },
      ],
    });

    const state = useChatStore.getState();
    expect(state.activeSessionId).toBe(ownId);
    expect(state.conversationRevision).toBe(7);
    expect(state.messages).toHaveLength(2);
  });
});
