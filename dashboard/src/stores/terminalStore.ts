/**
 * Terminal Store (Zustand)
 * =========================
 * Manages multiple terminal sessions (like VS Code's terminal tabs).
 * Each session has its own xterm.js instance and WebSocket connection.
 */

import { create } from 'zustand';

export interface TerminalSession {
  id: string;
  name: string;
  /** ISO timestamp of creation */
  createdAt: string;
}

export interface TerminalState {
  /** All terminal sessions */
  sessions: TerminalSession[];
  /** ID of the currently active terminal */
  activeSessionId: string | null;
  /** Whether the terminal panel is visible */
  visible: boolean;

  // Actions
  addSession: (name?: string) => string;
  closeSession: (id: string) => void;
  setActiveSession: (id: string) => void;
  renameSession: (id: string, name: string) => void;
  setVisible: (visible: boolean) => void;
  toggleVisible: () => void;
}

let terminalCounter = 1;

export function generateTerminalId(): string {
  return `term_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`;
}

export const useTerminalStore = create<TerminalState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  visible: false,

  addSession: (name?: string) => {
    const id = generateTerminalId();
    const sessionName = name || `Terminal ${terminalCounter++}`;
    const session: TerminalSession = {
      id,
      name: sessionName,
      createdAt: new Date().toISOString(),
    };
    set(state => ({
      sessions: [...state.sessions, session],
      activeSessionId: id,
      visible: true,
    }));
    return id;
  },

  closeSession: (id) => {
    set(state => {
      const remaining = state.sessions.filter(s => s.id !== id);
      let newActive = state.activeSessionId;
      if (state.activeSessionId === id) {
        // Switch to another session or null
        if (remaining.length > 0) {
          newActive = remaining[remaining.length - 1].id;
        } else {
          newActive = null;
        }
      }
      return {
        sessions: remaining,
        activeSessionId: newActive,
        visible: remaining.length > 0,
      };
    });
  },

  setActiveSession: (id) => {
    set({ activeSessionId: id, visible: true });
  },

  renameSession: (id, name) => {
    set(state => ({
      sessions: state.sessions.map(s =>
        s.id === id ? { ...s, name } : s
      ),
    }));
  },

  setVisible: (visible) => set({ visible }),
  toggleVisible: () => {
    const state = get();
    if (!state.visible && state.sessions.length === 0) {
      // Add a default terminal if none exist
      get().addSession();
    } else {
      set({ visible: !state.visible });
    }
  },
}));
