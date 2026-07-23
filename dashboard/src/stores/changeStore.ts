/**
 * Change Store (Zustand)
 * =======================
 * Manages proposed file changes, diffs, and approval workflow.
 * Powers the Phase 1 Diff View + Change Review System.
 */

import { create } from 'zustand';
import { diffLines } from 'diff';

/* ─── Types ───────────────────────────────────────────────── */

export type ChangeStatus = 'pending' | 'approved' | 'rejected' | 'applied' | 'failed';

export interface ProposedChange {
  id: string;
  filePath: string;
  fileName: string;
  originalContent: string;
  newContent: string;
  status: ChangeStatus;
  diffHtml?: string;
  diffStats?: { additions: number; deletions: number };
  createdAt: number;
  description?: string;
  language?: string;
}

export interface ChangeStoreState {
  // All proposed changes across the session
  changes: ProposedChange[];

  // Currently selected change for viewing
  selectedChangeId: string | null;

  // UI state
  panelVisible: boolean;
  panelMode: 'list' | 'diff';

  // Actions
  addChange: (change: Omit<ProposedChange, 'id' | 'createdAt' | 'status' | 'diffStats'>) => void;
  removeChange: (id: string) => void;
  approveChange: (id: string) => void;
  rejectChange: (id: string) => void;
  selectChange: (id: string | null) => void;
  setPanelVisible: (visible: boolean) => void;
  setPanelMode: (mode: 'list' | 'diff') => void;
  approveAll: () => void;
  rejectAll: () => void;
  markApplied: (id: string) => void;
  markFailed: (id: string, error?: string) => void;
  clearChanges: () => void;

  // Computed
  pendingCount: () => number;
  approvedCount: () => number;
  rejectedCount: () => number;
  appliedCount: () => number;
  getSelectedChange: () => ProposedChange | null;
}

let changeCounter = 0;

function computeDiffStats(
  original: string,
  modified: string,
): { diffHtml: string; additions: number; deletions: number } {
  const changes = diffLines(original, modified);
  let additions = 0;
  let deletions = 0;

  const diffHtml = changes
    .map((part) => {
      if (part.added) {
        additions += part.count || 0;
        return `<div class="diff-line diff-added"><span class="diff-gutter">+</span><span>${escapeHtml(part.value)}</span></div>`;
      }
      if (part.removed) {
        deletions += part.count || 0;
        return `<div class="diff-line diff-removed"><span class="diff-gutter">−</span><span>${escapeHtml(part.value)}</span></div>`;
      }
      return `<div class="diff-line diff-unchanged"><span class="diff-gutter" aria-hidden="true" style="opacity:0.3"> </span><span>${escapeHtml(part.value)}</span></div>`;
    })
    .join('');

  return { diffHtml, additions, deletions };
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n$/, '')
    .replace(/\n/g, '<br/>');
}

function generateChangeId(): string {
  changeCounter++;
  return `change_${Date.now()}_${changeCounter}`;
}

function inferLanguage(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase() || '';
  const langMap: Record<string, string> = {
    js: 'javascript', ts: 'typescript', tsx: 'typescript', jsx: 'javascript',
    py: 'python', rs: 'rust', go: 'go', java: 'java', kt: 'kotlin',
    swift: 'swift', c: 'c', cpp: 'cpp', h: 'c', hpp: 'cpp',
    css: 'css', scss: 'scss', less: 'less', html: 'html', htm: 'html',
    xml: 'xml', json: 'json', yaml: 'yaml', yml: 'yaml', md: 'markdown',
    sql: 'sql', sh: 'shell', bash: 'shell', zsh: 'shell',
    toml: 'ini', cfg: 'ini', conf: 'ini', ini: 'ini',
    txt: 'plaintext', log: 'plaintext', csv: 'plaintext',
    svg: 'xml', graphql: 'graphql', gql: 'graphql',
    dart: 'dart', lua: 'lua', r: 'r', ruby: 'ruby', rb: 'ruby',
    php: 'php', pl: 'perl', pm: 'perl',
  };
  return langMap[ext] || 'plaintext';
}

export const useChangeStore = create<ChangeStoreState>((set, get) => ({
  changes: [],
  selectedChangeId: null,
  panelVisible: false,
  panelMode: 'list',

  addChange: (change) => {
    const stats = computeDiffStats(change.originalContent, change.newContent);
    const newChange: ProposedChange = {
      ...change,
      id: generateChangeId(),
      status: 'pending',
      createdAt: Date.now(),
      diffHtml: stats.diffHtml,
      diffStats: { additions: stats.additions, deletions: stats.deletions },
      language: change.language || inferLanguage(change.fileName),
    };

    set((state) => ({
      changes: [newChange, ...state.changes],
      panelVisible: true,
      selectedChangeId: newChange.id,
    }));
  },

  removeChange: (id) => {
    set((state) => ({
      changes: state.changes.filter((c) => c.id !== id),
      selectedChangeId: state.selectedChangeId === id ? null : state.selectedChangeId,
    }));
  },

  approveChange: (id) => {
    set((state) => ({
      changes: state.changes.map((c) =>
        c.id === id ? { ...c, status: 'approved' as ChangeStatus } : c,
      ),
    }));
  },

  rejectChange: (id) => {
    set((state) => ({
      changes: state.changes.map((c) =>
        c.id === id ? { ...c, status: 'rejected' as ChangeStatus } : c,
      ),
    }));
  },

  selectChange: (id) => {
    set({ selectedChangeId: id, panelMode: id ? 'diff' : 'list' });
  },

  setPanelVisible: (visible) => set({ panelVisible: visible }),
  setPanelMode: (mode) => set({ panelMode: mode }),

  approveAll: () => {
    set((state) => ({
      changes: state.changes.map((c) =>
        c.status === 'pending' ? { ...c, status: 'approved' as ChangeStatus } : c,
      ),
    }));
  },

  rejectAll: () => {
    set((state) => ({
      changes: state.changes.map((c) =>
        c.status === 'pending' ? { ...c, status: 'rejected' as ChangeStatus } : c,
      ),
    }));
  },

  markApplied: (id) => {
    set((state) => ({
      changes: state.changes.map((c) =>
        c.id === id ? { ...c, status: 'applied' as ChangeStatus } : c,
      ),
    }));
  },

  markFailed: (id) => {
    set((state) => ({
      changes: state.changes.map((c) =>
        c.id === id ? { ...c, status: 'failed' as ChangeStatus } : c,
      ),
    }));
  },

  clearChanges: () => {
    set({ changes: [], selectedChangeId: null, panelVisible: false });
  },

  // Computed
  pendingCount: () => get().changes.filter((c) => c.status === 'pending').length,
  approvedCount: () => get().changes.filter((c) => c.status === 'approved').length,
  rejectedCount: () => get().changes.filter((c) => c.status === 'rejected').length,
  appliedCount: () => get().changes.filter((c) => c.status === 'applied').length,
  getSelectedChange: () => {
    const state = get();
    return state.changes.find((c) => c.id === state.selectedChangeId) || null;
  },
}));
