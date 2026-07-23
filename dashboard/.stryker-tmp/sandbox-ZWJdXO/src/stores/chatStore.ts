/**
 * Chat Store (Zustand)
 * =====================
 * Manages chat sessions, messages, streaming state, and model selection.
 */
// @ts-nocheck


import { create } from 'zustand';

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
      title: 'New Chat',
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

  addMessage: (msg: ChatMessage) => {
    const { messages, activeSessionId, sessions } = get();
    const newMessages = [...messages, msg];
    const updatedSessions = sessions.map(s =>
      s.id === activeSessionId
        ? { ...s, messages: newMessages, updatedAt: new Date().toISOString() }
        : s
    );
    set({ messages: newMessages, sessions: updatedSessions });
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
      const workspacePath = localStorage.getItem('agk_active_project') || '/';
      const saved = localStorage.getItem(STORAGE_KEY_PREFIX + workspacePath);
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

  saveToStorage: () => {
    try {
      const workspacePath = localStorage.getItem('agk_active_project') || '/';
      const { sessions, activeSessionId } = get();
      const payload = { sessions, activeSessionId };
      localStorage.setItem(STORAGE_KEY_PREFIX + workspacePath, JSON.stringify(payload));
    } catch (e) {
      console.error('[ChatStore] Failed to save to storage:', e);
    }
  },
}));
