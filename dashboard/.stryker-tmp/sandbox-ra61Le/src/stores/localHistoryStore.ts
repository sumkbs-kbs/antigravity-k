/**
 * Local History Store (Zustand)
 * ==============================
 * Tracks file snapshots over time — auto-saves on file changes,
 * supports comparing any two versions, and persists to localStorage.
 * Inspired by VS Code's Local History feature.
 */
// @ts-nocheck


import { create } from 'zustand';

/* ─── Types ────────────────────────────────────────────────── */

export type SnapshotSource = 'auto' | 'manual' | 'ai_change' | 'git_commit';

export interface FileSnapshot {
  id: string;
  filePath: string;
  fileName: string;
  timestamp: number;
  content: string;
  source: SnapshotSource;
  /** Label for AI changes */
  label?: string;
  /** Size in bytes */
  size: number;
}

export interface LocalHistoryState {
  /** All snapshots across all files */
  snapshots: Record<string, FileSnapshot[]>; // keyed by filePath
  /** Currently selected file for viewing */
  selectedFile: string | null;
  /** IDs of two snapshots being compared */
  compareIds: [string | null, string | null];
  /** Whether to auto-save snapshots on file changes */
  autoSaveEnabled: boolean;
  /** Max snapshots per file */
  maxSnapshotsPerFile: number;

  // Actions
  addSnapshot: (snapshot: Omit<FileSnapshot, 'id' | 'timestamp' | 'size'>, force?: boolean) => void;
  removeSnapshot: (filePath: string, snapshotId: string) => void;
  clearFileHistory: (filePath: string) => void;
  clearAllHistory: () => void;
  setSelectedFile: (filePath: string | null) => void;
  setComparePair: (idA: string | null, idB: string | null) => void;
  swapComparePair: () => void;
  setAutoSaveEnabled: (enabled: boolean) => void;
  setMaxSnapshotsPerFile: (max: number) => void;

  // Computed
  getSnapshotsForFile: (filePath: string) => FileSnapshot[];
  getAllFiles: () => Array<{ filePath: string; fileName: string; count: number; lastModified: number }>;
  getSnapshotById: (id: string | null) => FileSnapshot | null;
}

/* ─── Storage ──────────────────────────────────────────────── */

const STORAGE_KEY = 'agk_local_history';
function loadMaxSetting(): number {
  try {
    const raw = localStorage.getItem('agk_history_max');
    if (raw) {
      const val = parseInt(raw);
      if (!isNaN(val) && val >= 5 && val <= 200) return val;
    }
  } catch { /* ignore */ }
  return 50;
}

const DEFAULT_MAX_SNAPSHOTS = loadMaxSetting();

function loadFromStorage(): Record<string, FileSnapshot[]> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore corrupt data */ }
  return {};
}

function saveToStorage(snapshots: Record<string, FileSnapshot[]>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshots));
  } catch {
    // Storage full — silently fail
  }
}

/* ─── Helpers ──────────────────────────────────────────────── */

let snapshotCounter = 0;
const MAX_TOTAL_SNAPSHOTS = 2000;

function trimSnapshots(
  snapshots: Record<string, FileSnapshot[]>,
  maxPerFile: number,
): Record<string, FileSnapshot[]> {
  const result: Record<string, FileSnapshot[]> = {};
  let totalCount = 0;

  // Sort by timestamp descending for each file, keep newest
  for (const [filePath, snaps] of Object.entries(snapshots)) {
    const sorted = [...snaps].sort((a, b) => b.timestamp - a.timestamp);
    const trimmed = sorted.slice(0, maxPerFile);
    result[filePath] = trimmed;
    totalCount += trimmed.length;
  }

  // If still over global max, remove oldest across all files
  if (totalCount > MAX_TOTAL_SNAPSHOTS) {
    const all: Array<{ filePath: string; snapshot: FileSnapshot }> = [];
    for (const [filePath, snaps] of Object.entries(result)) {
      for (const snap of snaps) {
        all.push({ filePath, snapshot: snap });
      }
    }
    all.sort((a, b) => b.snapshot.timestamp - a.snapshot.timestamp);
    const kept = all.slice(0, MAX_TOTAL_SNAPSHOTS);
    const newResult: Record<string, FileSnapshot[]> = {};
    for (const { filePath, snapshot } of kept) {
      if (!newResult[filePath]) newResult[filePath] = [];
      newResult[filePath].push(snapshot);
    }
    return newResult;
  }

  return result;
}

/* ─── Store ────────────────────────────────────────────────── */

export const useLocalHistoryStore = create<LocalHistoryState>((set, get) => {
  const initial = loadFromStorage();

  return {
    snapshots: initial,
    selectedFile: null,
    compareIds: [null, null],
    autoSaveEnabled: true,
    maxSnapshotsPerFile: DEFAULT_MAX_SNAPSHOTS,

    addSnapshot: (snapshot, force = false) => {
      const state = get();
      if (!force && !state.autoSaveEnabled) return;

      const id = `snap_${Date.now()}_${++snapshotCounter}`;
      const newSnapshot: FileSnapshot = {
        ...snapshot,
        id,
        timestamp: Date.now(),
        size: new Blob([snapshot.content]).size,
      };

      set(prev => {
        const existing = prev.snapshots[snapshot.filePath] || [];
        const updated = {
          ...prev.snapshots,
          [snapshot.filePath]: [...existing, newSnapshot],
        };
        const trimmed = trimSnapshots(updated, prev.maxSnapshotsPerFile);
        // Persist async
        setTimeout(() => saveToStorage(trimmed), 0);
        return { snapshots: trimmed };
      });
    },

    removeSnapshot: (filePath, snapshotId) => {
      set(prev => {
        const snaps = (prev.snapshots[filePath] || []).filter(s => s.id !== snapshotId);
        const updated = { ...prev.snapshots };
        if (snaps.length === 0) {
          delete updated[filePath];
        } else {
          updated[filePath] = snaps;
        }
        setTimeout(() => saveToStorage(updated), 0);
        return { snapshots: updated };
      });
    },

    clearFileHistory: (filePath) => {
      set(prev => {
        const updated = { ...prev.snapshots };
        delete updated[filePath];
        // Also update selection
        const newSelected = prev.selectedFile === filePath ? null : prev.selectedFile;
        setTimeout(() => saveToStorage(updated), 0);
        return { snapshots: updated, selectedFile: newSelected, compareIds: [null, null] };
      });
    },

    clearAllHistory: () => {
      set({ snapshots: {}, selectedFile: null, compareIds: [null, null] });
      localStorage.removeItem(STORAGE_KEY);
    },

    setSelectedFile: (filePath) => {
      set({ selectedFile: filePath, compareIds: [null, null] });
    },

    setComparePair: (idA, idB) => {
      set({ compareIds: [idA, idB] });
    },

    swapComparePair: () => {
      set(prev => ({
        compareIds: [prev.compareIds[1], prev.compareIds[0]],
      }));
    },

    setAutoSaveEnabled: (enabled) => set({ autoSaveEnabled: enabled }),

    setMaxSnapshotsPerFile: (max) => {
      const clamped = Math.max(5, Math.min(200, max));
      const state = get();
      const trimmed = trimSnapshots(state.snapshots, clamped);
      saveToStorage(trimmed);
      // Also persist the max setting
      localStorage.setItem('agk_history_max', String(clamped));
      set({ maxSnapshotsPerFile: clamped, snapshots: trimmed });
    },

    // Computed
    getSnapshotsForFile: (filePath) => {
      return get().snapshots[filePath] || [];
    },

    getAllFiles: () => {
      const state = get();
      const files: Array<{ filePath: string; fileName: string; count: number; lastModified: number }> = [];
      for (const [filePath, snaps] of Object.entries(state.snapshots)) {
        if (snaps.length === 0) continue;
        const name = filePath.split('/').pop() || filePath;
        const lastModified = Math.max(...snaps.map(s => s.timestamp));
        files.push({ filePath, fileName: name, count: snaps.length, lastModified });
      }
      files.sort((a, b) => b.lastModified - a.lastModified);
      return files;
    },

    getSnapshotById: (id) => {
      if (!id) return null;
      const state = get();
      for (const snaps of Object.values(state.snapshots)) {
        const found = snaps.find(s => s.id === id);
        if (found) return found;
      }
      return null;
    },
  };
});
