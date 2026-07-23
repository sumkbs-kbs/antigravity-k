/**
 * Output Store (Zustand)
 * =======================
 * Manages output logs from various sources: tool execution, build processes,
 * AI agent events, etc. Acts like VS Code's Output panel with source filtering.
 */

import { create } from 'zustand';

export type OutputLevel = 'info' | 'success' | 'warn' | 'error' | 'debug';

export const OUTPUT_SOURCES = {
  SYSTEM: 'System',
  TOOL: 'Tool',
  BUILD: 'Build',
  AGENT: 'Agent',
  TERMINAL: 'Terminal',
  GIT: 'Git',
} as const;

export type OutputSource = (typeof OUTPUT_SOURCES)[keyof typeof OUTPUT_SOURCES];

export interface OutputEntry {
  id: string;
  timestamp: string;
  source: OutputSource;
  level: OutputLevel;
  message: string;
  /** Optional structured data */
  data?: Record<string, any>;
}

export interface OutputState {
  entries: OutputEntry[];
  /** Active source filter (null = show all) */
  activeSource: OutputSource | null;
  /** Maximum entries to keep (ring buffer) */
  maxEntries: number;

  // Actions
  addOutput: (entry: Omit<OutputEntry, 'id' | 'timestamp'>) => void;
  clearOutput: () => void;
  setActiveSource: (source: OutputSource | null) => void;
}

let outputCounter = 0;
const MAX_ENTRIES = 5000;

export const useOutputStore = create<OutputState>((set, get) => ({
  entries: [],
  activeSource: null,
  maxEntries: MAX_ENTRIES,

  addOutput: (entry) => {
    const id = `out_${Date.now()}_${++outputCounter}`;
    const newEntry: OutputEntry = {
      ...entry,
      id,
      timestamp: new Date().toISOString(),
    };
    set(state => {
      const entries = [...state.entries, newEntry];
      // Ring buffer: trim oldest entries if over limit
      if (entries.length > state.maxEntries) {
        return { entries: entries.slice(-state.maxEntries) };
      }
      return { entries };
    });
  },

  clearOutput: () => set({ entries: [] }),

  setActiveSource: (source) => set({ activeSource: source }),
}));

/* ─── Convenience helpers ──────────────────────────────────── */

export function logOutput(
  message: string,
  source: OutputSource = OUTPUT_SOURCES.SYSTEM,
  level: OutputLevel = 'info',
  data?: Record<string, any>,
) {
  useOutputStore.getState().addOutput({ source, level, message, data });
}

export function logToolOutput(message: string, data?: Record<string, any>) {
  logOutput(message, OUTPUT_SOURCES.TOOL, 'info', data);
}

export function logBuildOutput(message: string, level: OutputLevel = 'info') {
  logOutput(message, OUTPUT_SOURCES.BUILD, level);
}

export function logAgentOutput(message: string, level: OutputLevel = 'info') {
  logOutput(message, OUTPUT_SOURCES.AGENT, level);
}

export function logError(message: string, source: OutputSource = OUTPUT_SOURCES.SYSTEM) {
  logOutput(message, source, 'error');
}
