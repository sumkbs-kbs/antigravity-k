import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore, generateChatTitle } from '../chatStore';

describe('chatStore sessions & auto-title', () => {
  beforeEach(() => {
    useChatStore.setState({
      sessions: [],
      activeSessionId: null,
      activeSession: null,
      messages: [],
    });
  });

  describe('generateChatTitle', () => {
    it('returns default for empty content', () => {
      expect(generateChatTitle('')).toBe('새 대화');
    });

    it('cleans markdown headers, codeblocks, and think tags', () => {
      const content = '# 제목입니다\n```ts\nconst a = 1;\n```\n내용입니다';
      expect(generateChatTitle(content)).toBe('제목입니다');
    });

    it('truncates long content cleanly with ellipsis', () => {
      const content = '이것은 매우 긴 사용자의 첫 번째 질문 프롬프트 텍스트로서 제목 길이를 초과하는 경우입니다.';
      const title = generateChatTitle(content);
      expect(title.length).toBeLessThanOrEqual(30);
      expect(title).toMatch(/\.\.\.$/);
    });
  });

  describe('auto title derivation on first user message', () => {
    it('automatically updates session title on first user message', () => {
      useChatStore.getState().createNewSession();
      const initialSession = useChatStore.getState().activeSession;
      expect(initialSession?.title).toBe('새 대화');

      useChatStore.getState().addMessage({
        role: 'user',
        content: '인공지능 모델 벤치마크 테스트해줘',
      });

      const updatedSession = useChatStore.getState().activeSession;
      expect(updatedSession?.title).toBe('인공지능 모델 벤치마크 테스트해줘');
    });

    it('does not overwrite title if user has already customized it', () => {
      useChatStore.getState().createNewSession();
      const sessionId = useChatStore.getState().activeSessionId!;
      useChatStore.getState().updateSessionTitle(sessionId, '내 맞춤 프로젝트 대화');

      useChatStore.getState().addMessage({
        role: 'user',
        content: '새로운 질문입니다',
      });

      expect(useChatStore.getState().activeSession?.title).toBe('내 맞춤 프로젝트 대화');
    });
  });

  describe('updateSessionTitle & deleteSession', () => {
    it('updates session title via updateSessionTitle', () => {
      useChatStore.getState().createNewSession();
      const sessionId = useChatStore.getState().activeSessionId!;

      useChatStore.getState().updateSessionTitle(sessionId, '변경된 제목');
      expect(useChatStore.getState().activeSession?.title).toBe('변경된 제목');
      expect(useChatStore.getState().sessions.find(s => s.id === sessionId)?.title).toBe('변경된 제목');
    });

    it('deletes session via deleteSession', () => {
      useChatStore.getState().createNewSession();
      const sessionId = useChatStore.getState().activeSessionId!;
      expect(useChatStore.getState().sessions.length).toBe(1);

      useChatStore.getState().deleteSession(sessionId);
      expect(useChatStore.getState().activeSessionId).not.toBe(sessionId);
    });
  });
});
