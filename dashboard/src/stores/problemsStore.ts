/**
 * Problems Store (Zustand)
 * =========================
 * Manages diagnostics (errors, warnings, info) from Monaco's built-in
 * TypeScript/JavaScript language service and other language providers.
 * Mirrors VS Code's Problems panel behavior.
 */

import { create } from 'zustand';

export type ProblemSeverity = 'error' | 'warning' | 'info';

export interface Problem {
  id: string;
  filePath: string;
  fileName: string;
  message: string;
  severity: ProblemSeverity;
  line: number;
  column: number;
  endLine?: number;
  endColumn?: number;
  code?: string;
  source?: string;
}

/* ─── Marker data shape from Monaco (not importing monaco-editor directly) ── */

export interface MonacoMarker {
  message: string;
  severity: number; // 8=error, 4=warning, 2=info, 1=hint
  startLineNumber: number;
  startColumn: number;
  endLineNumber: number;
  endColumn: number;
  code?: string | { value: string; target: string };
  source?: string;
}

export interface ProblemsState {
  problems: Problem[];
  activeFilePath: string | null;
  filterSeverity: ProblemSeverity | 'all';
  filterText: string;
  problemsPanelVisible: boolean;

  // Derived counts
  errorCount: () => number;
  warningCount: () => number;
  infoCount: () => number;
  totalCount: () => number;

  // Actions
  setProblems: (filePath: string, fileName: string, markers: MonacoMarker[]) => void;
  clearProblems: (filePath?: string) => void;
  clearAll: () => void;
  setActiveFile: (path: string | null) => void;
  setFilterSeverity: (severity: ProblemSeverity | 'all') => void;
  setFilterText: (text: string) => void;
  setProblemsPanelVisible: (visible: boolean) => void;
  toggleProblemsPanel: () => void;
}

let problemIdCounter = 0;

/* ─── Monaco MarkerSeverity constants (8=Error, 4=Warning, 2=Info) ── */

function severityFromMonaco(severity: number): ProblemSeverity {
  if (severity >= 8) return 'error';
  if (severity >= 4) return 'warning';
  return 'info';
}

export const useProblemsStore = create<ProblemsState>((set, get) => ({
  problems: [],
  activeFilePath: null,
  filterSeverity: 'all',
  filterText: '',
  problemsPanelVisible: false,

  errorCount: () => get().problems.filter(p => p.severity === 'error').length,
  warningCount: () => get().problems.filter(p => p.severity === 'warning').length,
  infoCount: () => get().problems.filter(p => p.severity === 'info').length,
  totalCount: () => get().problems.length,

  setProblems: (filePath, fileName, markers) => {
    // Remove existing problems for this file
    const existing = get().problems.filter(p => p.filePath !== filePath);

    // Convert markers to problems
    const newProblems: Problem[] = markers.map(marker => ({
      id: `problem-${++problemIdCounter}`,
      filePath,
      fileName,
      message: marker.message,
      severity: severityFromMonaco(marker.severity),
      line: marker.startLineNumber,
      column: marker.startColumn,
      endLine: marker.endLineNumber,
      endColumn: marker.endColumn,
      code: typeof marker.code === 'string' ? marker.code : undefined,
      source: marker.source || 'typescript',
    }));

    set({ problems: [...existing, ...newProblems] });
  },

  clearProblems: (filePath) => {
    if (filePath) {
      set(state => ({ problems: state.problems.filter(p => p.filePath !== filePath) }));
    } else {
      set({ problems: [] });
    }
  },

  clearAll: () => set({ problems: [] }),

  setActiveFile: (path) => set({ activeFilePath: path }),

  setFilterSeverity: (severity) => set({ filterSeverity: severity }),

  setFilterText: (text) => set({ filterText: text }),

  setProblemsPanelVisible: (visible) => set({ problemsPanelVisible: visible }),

  toggleProblemsPanel: () => set(state => ({ problemsPanelVisible: !state.problemsPanelVisible })),
}));

/* ─── Utility: Filter problems by active file, severity, and text ─ */

export function getFilteredProblems(
  problems: Problem[],
  activeFilePath: string | null,
  filterSeverity: ProblemSeverity | 'all',
  filterText: string,
): Problem[] {
  let filtered = problems;

  // Filter by active file (or show all if no active file)
  if (activeFilePath) {
    filtered = filtered.filter(p => p.filePath === activeFilePath);
  }

  // Filter by severity
  if (filterSeverity !== 'all') {
    filtered = filtered.filter(p => p.severity === filterSeverity);
  }

  // Filter by text search
  if (filterText.trim()) {
    const lower = filterText.toLowerCase();
    filtered = filtered.filter(p =>
      p.message.toLowerCase().includes(lower) ||
      p.fileName.toLowerCase().includes(lower) ||
      p.code?.toLowerCase().includes(lower)
    );
  }

  // Sort by line number
  return filtered.sort((a, b) => a.line - b.line || a.column - b.column);
}
