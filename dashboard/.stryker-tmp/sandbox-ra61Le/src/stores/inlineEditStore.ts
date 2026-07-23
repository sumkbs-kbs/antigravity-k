/**
 * Inline Edit Store (Zustand)
 * =============================
 * Manages Cursor-style inline code editing state:
 * - Ctrl+K: Opens inline edit mode at cursor position
 * - User types instruction → gets AI suggestion
 * - Tab to accept, Esc to cancel
 */
// @ts-nocheck


import { create } from 'zustand';

export type InlineEditPhase = 'idle' | 'input' | 'loading' | 'preview' | 'applied';

export interface InlineEditState {
  phase: InlineEditPhase;
  /** Current file path being edited */
  filePath: string | null;
  /** Current cursor line number */
  cursorLine: number;
  /** Current cursor column */
  cursorColumn: number;
  /** User's edit instruction text */
  instruction: string;
  /** Original code (before edit) shown in the ghost text */
  originalCode: string;
  /** AI suggestion code */
  suggestedCode: string;
  /** Error message if suggestion failed */
  error: string | null;
  /** The line range being edited */
  startLine: number;
  endLine: number;

  // Actions
  openEditor: (filePath: string, line: number, column: number) => void;
  closeEditor: () => void;
  setInstruction: (instruction: string) => void;
  setSuggestedCode: (code: string, startLine: number, endLine: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  applySuggestion: () => void;
  rejectSuggestion: () => void;
}

export const useInlineEditStore = create<InlineEditState>((set, get) => ({
  phase: 'idle',
  filePath: null,
  cursorLine: 1,
  cursorColumn: 1,
  instruction: '',
  originalCode: '',
  suggestedCode: '',
  error: null,
  startLine: 1,
  endLine: 1,

  openEditor: (filePath, line, column) => {
    set({
      phase: 'input',
      filePath,
      cursorLine: line,
      cursorColumn: column,
      instruction: '',
      originalCode: '',
      suggestedCode: '',
      error: null,
      startLine: line,
      endLine: line,
    });
  },

  closeEditor: () => {
    set({
      phase: 'idle',
      filePath: null,
      instruction: '',
      originalCode: '',
      suggestedCode: '',
      error: null,
    });
  },

  setInstruction: (instruction) => set({ instruction }),

  setSuggestedCode: (code, startLine, endLine) => {
    set({
      phase: 'preview',
      suggestedCode: code,
      startLine,
      endLine,
      error: null,
    });
  },

  setLoading: (loading) => {
    set({ phase: loading ? 'loading' : get().phase === 'loading' ? 'input' : get().phase });
  },

  setError: (error) => set({ error, phase: 'input' }),

  applySuggestion: () => {
    set({ phase: 'applied' });
  },

  rejectSuggestion: () => {
    set({
      phase: 'idle',
      instruction: '',
      originalCode: '',
      suggestedCode: '',
      error: null,
    });
  },
}));
