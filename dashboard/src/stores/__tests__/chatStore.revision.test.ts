/**
 * CTX-01: chatStore mirrors authoritative conversation revision.
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { useChatStore } from '../chatStore';

describe('chatStore conversation revision (CTX-01)', () => {
  beforeEach(() => {
    useChatStore.setState({
      sessions: [],
      activeSessionId: null,
      activeSession: null,
      messages: [],
      conversationRevision: 0,
      isStreaming: false,
      currentAssistantContent: '',
    });
    useChatStore.getState().createNewSession();
  });

  it('starts new sessions at revision 0', () => {
    const state = useChatStore.getState();
    expect(state.conversationRevision).toBe(0);
    expect(state.activeSession?.conversationRevision).toBe(0);
  });

  it('applyServerSnapshot updates revision without treating client array as SoT', () => {
    useChatStore.getState().addMessage({ role: 'user', content: 'local-only' });
    useChatStore.getState().applyServerSnapshot({
      conversation_id: useChatStore.getState().activeSessionId!,
      revision: 4,
      summary: 'server summary',
      retained_message_ids: ['msg_a', 'msg_b'],
      messages: [
        { role: 'system', content: 'server summary', id: 'msg_summary' },
        { role: 'user', content: 'retained', id: 'msg_a' },
      ],
    });
    const state = useChatStore.getState();
    expect(state.conversationRevision).toBe(4);
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0].content).toBe('server summary');
    expect(state.activeSession?.conversationRevision).toBe(4);
  });

  it('setConversationRevision persists on active session', () => {
    useChatStore.getState().setConversationRevision(7);
    expect(useChatStore.getState().conversationRevision).toBe(7);
    expect(useChatStore.getState().activeSession?.conversationRevision).toBe(7);
  });
});
