/**
 * Chat Store (Zustand)
 * =====================
 * Manages chat sessions, messages, streaming state, and model selection.
 */

import { create } from 'zustand';
import { useProjectStore } from './projectStore';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  id?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  updatedAt: string;
  messages: ChatMessage[];
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 8);
}

export function generateChatTitle(content: string): string {
  if (!content) return '새 대화';
  // Strip code blocks, think blocks, html tags, markdown formatting
  const cleaned = content
    .replace(/```[\s\S]*?```/g, '')
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .replace(/^#+\s*/, '')
    .replace(/^[>\s*-]+/gm, '')
    .trim();

  const firstLine = cleaned.split('\n').map(l => l.trim()).find(l => l.length > 0) || content.trim();
  if (firstLine.length <= 28) {
    return firstLine;
  }
  return firstLine.slice(0, 26) + '...';
}

export interface ChatState {
  // Sessions
  sessions: ChatSession[];
  activeSessionId: string | null;
  activeSession: ChatSession | null;

  // Messages
  messages: ChatMessage[];
  isStreaming: boolean;
  currentAssistantContent: string;

  // Models
  models: Array<{ id: string; role?: string; description?: string }>;
  selectedModel: string;

  // ToDos
  isPlanMode: boolean;
  isTddMode: boolean;

  // Actions
  createNewSession: () => void;
  switchSession: (id: string) => void;
  deleteSession: (id: string) => void;
  updateSessionTitle: (id: string, title: string) => void;
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistantMessage: (content: string) => void;
  setStreaming: (val: boolean) => void;
  setCurrentAssistantContent: (content: string) => void;
  appendToCurrentAssistantContent: (chunk: string) => void;
  setModels: (models: Array<{ id: string; role?: string; description?: string }>) => void;
  setSelectedModel: (model: string) => void;
  setPlanMode: (val: boolean) => void;
  setTddMode: (val: boolean) => void;
  loadFromStorage: () => void;
  saveToStorage: () => void;
  clearForProjectSwitch: () => void;
}

const STORAGE_KEY_PREFIX = 'antigravity_chat_';

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  activeSession: null,
  messages: [],
  isStreaming: false,
  currentAssistantContent: '',
  models: [],
  selectedModel: 'default',
  isPlanMode: false,
  isTddMode: false,

  createNewSession: () => {
    const id = generateId();
    const session: ChatSession = {
      id,
      title: '새 대화',
      updatedAt: new Date().toISOString(),
      messages: [],
    };
    set({
      activeSessionId: id,
      activeSession: session,
      messages: [],
      sessions: [session, ...get().sessions.filter(s => s.id !== id)],
    });
    get().saveToStorage();
  },

  switchSession: (id: string) => {
    const session = get().sessions.find(s => s.id === id);
    if (session) {
      set({
        activeSessionId: id,
        activeSession: session,
        messages: session.messages,
      });
    }
  },

  deleteSession: (id: string) => {
    const { sessions, activeSessionId } = get();
    const filtered = sessions.filter(s => s.id !== id);
    set({ sessions: filtered });

    if (activeSessionId === id) {
      if (filtered.length > 0) {
        get().switchSession(filtered[0].id);
      } else {
        get().createNewSession();
      }
    } else {
      get().saveToStorage();
    }
  },

  updateSessionTitle: (id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return;
    const { sessions, activeSessionId, activeSession } = get();
    const updatedSessions = sessions.map(s =>
      s.id === id ? { ...s, title: trimmed, updatedAt: new Date().toISOString() } : s
    );
    const updatedActive = activeSession && activeSession.id === id
      ? { ...activeSession, title: trimmed, updatedAt: new Date().toISOString() }
      : activeSession;
    set({ sessions: updatedSessions, activeSession: updatedActive });
    get().saveToStorage();
  },

  addMessage: (msg: ChatMessage) => {
    const { messages, activeSessionId, sessions, activeSession } = get();
    const newMessages = [...messages, msg];

    let derivedTitle: string | undefined;
    const currentSession = sessions.find(s => s.id === activeSessionId) || activeSession;
    const isDefaultTitle = !currentSession?.title ||
      currentSession.title === 'New Chat' ||
      currentSession.title === '새 작업' ||
      currentSession.title === '새 채팅' ||
      currentSession.title === '새 대화' ||
      currentSession.title === '대화';

    if (msg.role === 'user' && isDefaultTitle && msg.content.trim()) {
      derivedTitle = generateChatTitle(msg.content);
    }

    const updatedSessions = sessions.map(s => {
      if (s.id !== activeSessionId) return s;
      return {
        ...s,
        messages: newMessages,
        title: derivedTitle || s.title,
        updatedAt: new Date().toISOString(),
      };
    });

    const updatedActive = activeSession && activeSession.id === activeSessionId
      ? {
          ...activeSession,
          messages: newMessages,
          title: derivedTitle || activeSession.title,
          updatedAt: new Date().toISOString(),
        }
      : activeSession;

    set({ messages: newMessages, sessions: updatedSessions, activeSession: updatedActive });
    get().saveToStorage();
  },

  updateLastAssistantMessage: (content: string) => {
    const { messages, activeSessionId, sessions } = get();
    const newMessages = [...messages];
    if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
      newMessages[newMessages.length - 1] = { ...newMessages[newMessages.length - 1], content };
    } else {
      newMessages.push({ role: 'assistant', content });
    }
    const updatedSessions = sessions.map(s =>
      s.id === activeSessionId
        ? { ...s, messages: newMessages, updatedAt: new Date().toISOString() }
        : s
    );
    set({ messages: newMessages, sessions: updatedSessions });
  },

  setStreaming: (val: boolean) => set({ isStreaming: val }),
  setCurrentAssistantContent: (content: string) => set({ currentAssistantContent: content }),
  appendToCurrentAssistantContent: (chunk: string) =>
    set(state => ({ currentAssistantContent: state.currentAssistantContent + chunk })),

  setModels: (models) => set({ models }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setPlanMode: (val: boolean) => set({ isPlanMode: val }),
  setTddMode: (val: boolean) => set({ isTddMode: val }),

  loadFromStorage: () => {
    try {
      const project = useProjectStore.getState();
      const storageKey = project.activeProjectId
        || project.activeProjectPath
        || localStorage.getItem('agk_active_project')
        || '/';
      const saved = localStorage.getItem(STORAGE_KEY_PREFIX + storageKey);
      if (!saved) return;

      const parsed = JSON.parse(saved);
      if (parsed.sessions && parsed.sessions.length > 0) {
        const sessions = parsed.sessions;
        const activeSessionId = parsed.activeSessionId || sessions[0].id;
        const activeSession = sessions.find((s: ChatSession) => s.id === activeSessionId) || sessions[0];
        set({
          sessions,
          activeSessionId,
          activeSession,
          messages: activeSession.messages || [],
        });
      }
    } catch (e) {
      console.error('[ChatStore] Failed to load from storage:', e);
    }
  },

  clearForProjectSwitch: () => {
    set({
      sessions: [],
      activeSessionId: null,
      activeSession: null,
      messages: [],
      isStreaming: false,
      currentAssistantContent: '',
    });
  },

  saveToStorage: () => {
    try {
      const project = useProjectStore.getState();
      const storageKey = project.activeProjectId
        || project.activeProjectPath
        || localStorage.getItem('agk_active_project')
        || '/';
      const { sessions, activeSessionId } = get();
      const payload = { sessions, activeSessionId };
      localStorage.setItem(STORAGE_KEY_PREFIX + storageKey, JSON.stringify(payload));
    } catch (e) {
      console.error('[ChatStore] Failed to save to storage:', e);
    }
  },
}));
