/**
 * localHistoryStore Tests
 * ========================
 * Tests for the Zustand local history store — snapshot CRUD, comparison,
 * autoSave toggle, max snapshots per file, computed helpers.
 * Phase 8 (Local History Timeline) core functionality.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useLocalHistoryStore, type FileSnapshot } from '../localHistoryStore';

function makeSnapshot(overrides: Partial<FileSnapshot> = {}): any {
  return {
    filePath: 'test.ts',
    fileName: 'test.ts',
    content: 'console.log("hello")',
    source: 'auto' as const,
    ...overrides,
  };
}

beforeEach(() => {
  useLocalHistoryStore.setState({
    snapshots: {},
    selectedFile: null,
    compareIds: [null, null],
    autoSaveEnabled: true,
    maxSnapshotsPerFile: 50,
  });
});

describe('useLocalHistoryStore', () => {
  /* ─── Initial State ─────────────────────────────────────── */

  it('starts with empty snapshots and no selection', () => {
    const state = useLocalHistoryStore.getState();
    expect(state.snapshots).toEqual({});
    expect(state.selectedFile).toBeNull();
    expect(state.compareIds).toEqual([null, null]);
    expect(state.autoSaveEnabled).toBe(true);
    expect(state.maxSnapshotsPerFile).toBeGreaterThanOrEqual(5);
  });

  /* ─── addSnapshot ───────────────────────────────────────── */

  it('adds a snapshot with generated id, timestamp, and size', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot());

    const snaps = useLocalHistoryStore.getState().snapshots['test.ts'];
    expect(snaps).toHaveLength(1);
    expect(snaps[0].id).toMatch(/^snap_/);
    expect(snaps[0].timestamp).toBeGreaterThan(0);
    expect(snaps[0].size).toBeGreaterThan(0);
    expect(snaps[0].content).toBe('console.log("hello")');
    expect(snaps[0].source).toBe('auto');
  });

  it('adds a snapshot with label and custom source', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({
      filePath: 'manual.ts',
      fileName: 'manual.ts',
      content: 'saved',
      source: 'manual',
      label: '💾 저장 시점',
    }));

    const snap = useLocalHistoryStore.getState().snapshots['manual.ts'][0];
    expect(snap.label).toBe('💾 저장 시점');
    expect(snap.source).toBe('manual');
  });

  it('does not add snapshot when autoSave is disabled (unless forced)', () => {
    useLocalHistoryStore.getState().setAutoSaveEnabled(false);

    useLocalHistoryStore.getState().addSnapshot(makeSnapshot());
    expect(useLocalHistoryStore.getState().snapshots['test.ts']).toBeUndefined();
  });

  it('adds snapshot when forced even if autoSave is disabled', () => {
    useLocalHistoryStore.getState().setAutoSaveEnabled(false);

    useLocalHistoryStore.getState().addSnapshot(makeSnapshot(), true);

    const snaps = useLocalHistoryStore.getState().snapshots['test.ts'];
    expect(snaps).toHaveLength(1);
  });

  it('stores snapshots keyed by filePath', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts' }));
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'b.ts', fileName: 'b.ts' }));

    const state = useLocalHistoryStore.getState();
    expect(Object.keys(state.snapshots)).toHaveLength(2);
    expect(state.snapshots['a.ts']).toHaveLength(1);
    expect(state.snapshots['b.ts']).toHaveLength(1);
  });

  it('appends snapshots to the same file', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: 'v1' }));
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: 'v2' }));

    expect(useLocalHistoryStore.getState().snapshots['test.ts']).toHaveLength(2);
  });

  /* ─── removeSnapshot ────────────────────────────────────── */

  it('removes a snapshot by id', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: 'v1' }));
    const id = useLocalHistoryStore.getState().snapshots['test.ts'][0].id;
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: 'v2' }));

    useLocalHistoryStore.getState().removeSnapshot('test.ts', id);

    const remaining = useLocalHistoryStore.getState().snapshots['test.ts'];
    expect(remaining).toHaveLength(1);
    expect(remaining[0].content).toBe('v2');
  });

  it('deletes the file entry when last snapshot is removed', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: 'v1' }));
    const id = useLocalHistoryStore.getState().snapshots['test.ts'][0].id;

    useLocalHistoryStore.getState().removeSnapshot('test.ts', id);

    expect(useLocalHistoryStore.getState().snapshots['test.ts']).toBeUndefined();
  });

  /* ─── clearFileHistory ──────────────────────────────────── */

  it('clears all snapshots for a file', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts' }));
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'b.ts', fileName: 'b.ts' }));

    useLocalHistoryStore.getState().clearFileHistory('a.ts');

    const state = useLocalHistoryStore.getState();
    expect(state.snapshots['a.ts']).toBeUndefined();
    expect(state.snapshots['b.ts']).toHaveLength(1);
  });

  it('resets selection if cleared file was selected', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot());
    useLocalHistoryStore.getState().setSelectedFile('test.ts');

    useLocalHistoryStore.getState().clearFileHistory('test.ts');

    expect(useLocalHistoryStore.getState().selectedFile).toBeNull();
  });

  /* ─── clearAllHistory ───────────────────────────────────── */

  it('clears all snapshots and resets selection', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts' }));
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'b.ts', fileName: 'b.ts' }));
    useLocalHistoryStore.getState().setSelectedFile('a.ts');
    useLocalHistoryStore.getState().setComparePair('some-id', null);

    useLocalHistoryStore.getState().clearAllHistory();

    const state = useLocalHistoryStore.getState();
    expect(state.snapshots).toEqual({});
    expect(state.selectedFile).toBeNull();
    expect(state.compareIds).toEqual([null, null]);
  });

  /* ─── setSelectedFile ───────────────────────────────────── */

  it('sets the selected file and resets compare IDs', () => {
    useLocalHistoryStore.getState().setComparePair('id-a', 'id-b');
    useLocalHistoryStore.getState().setSelectedFile('test.ts');

    expect(useLocalHistoryStore.getState().selectedFile).toBe('test.ts');
    expect(useLocalHistoryStore.getState().compareIds).toEqual([null, null]);
  });

  /* ─── setComparePair / swapComparePair ───────────────────── */

  it('sets the compare pair', () => {
    useLocalHistoryStore.getState().setComparePair('a', 'b');
    expect(useLocalHistoryStore.getState().compareIds).toEqual(['a', 'b']);
  });

  it('sets individual IDs to null', () => {
    useLocalHistoryStore.getState().setComparePair(null, null);
    expect(useLocalHistoryStore.getState().compareIds).toEqual([null, null]);
  });

  it('swaps the compare pair', () => {
    useLocalHistoryStore.getState().setComparePair('a', 'b');
    useLocalHistoryStore.getState().swapComparePair();

    expect(useLocalHistoryStore.getState().compareIds).toEqual(['b', 'a']);
  });

  /* ─── setAutoSaveEnabled ─────────────────────────────────- */

  it('toggles auto-save', () => {
    useLocalHistoryStore.getState().setAutoSaveEnabled(false);
    expect(useLocalHistoryStore.getState().autoSaveEnabled).toBe(false);

    useLocalHistoryStore.getState().setAutoSaveEnabled(true);
    expect(useLocalHistoryStore.getState().autoSaveEnabled).toBe(true);
  });

  /* ─── setMaxSnapshotsPerFile ──────────────────────────────── */

  it('sets max snapshots per file with clamping (min 5)', () => {
    useLocalHistoryStore.getState().setMaxSnapshotsPerFile(2);
    expect(useLocalHistoryStore.getState().maxSnapshotsPerFile).toBe(5);
  });

  it('sets max snapshots per file with clamping (max 200)', () => {
    useLocalHistoryStore.getState().setMaxSnapshotsPerFile(500);
    expect(useLocalHistoryStore.getState().maxSnapshotsPerFile).toBe(200);
  });

  it('trims existing snapshots when max is reduced', () => {
    useLocalHistoryStore.getState().setMaxSnapshotsPerFile(50);
    for (let i = 0; i < 10; i++) {
      useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: `v${i}` }));
    }

    useLocalHistoryStore.getState().setMaxSnapshotsPerFile(5);

    expect(useLocalHistoryStore.getState().snapshots['test.ts']).toHaveLength(5);
  });

  /* ─── Computed: getSnapshotsForFile ──────────────────────── */

  it('returns snapshots for a file', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot());

    const snaps = useLocalHistoryStore.getState().getSnapshotsForFile('test.ts');
    expect(snaps).toHaveLength(1);
  });

  it('returns empty array for a file with no snapshots', () => {
    const snaps = useLocalHistoryStore.getState().getSnapshotsForFile('nonexistent.ts');
    expect(snaps).toEqual([]);
  });

  /* ─── Computed: getAllFiles ──────────────────────────────── */

  it('returns all files with metadata', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts' }));
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts', content: 'v2' }));
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'b.ts', fileName: 'b.ts' }));

    const files = useLocalHistoryStore.getState().getAllFiles();
    expect(files).toHaveLength(2);

    const fileA = files.find(f => f.filePath === 'a.ts');
    expect(fileA).toBeDefined();
    expect(fileA!.count).toBe(2);
    expect(fileA!.fileName).toBe('a.ts');

    const fileB = files.find(f => f.filePath === 'b.ts');
    expect(fileB).toBeDefined();
    expect(fileB!.count).toBe(1);
  });

  it('returns files sorted by lastModified descending', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'old.ts', fileName: 'old.ts' }));
    // Use fake timers to ensure timestamps differ for sort order
    vi.useFakeTimers();
    vi.advanceTimersByTime(100);
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'new.ts', fileName: 'new.ts' }));
    vi.useRealTimers();

    const files = useLocalHistoryStore.getState().getAllFiles();
    expect(files[0].filePath).toBe('new.ts');
    expect(files[1].filePath).toBe('old.ts');
  });

  it('returns empty array when no snapshots exist', () => {
    expect(useLocalHistoryStore.getState().getAllFiles()).toEqual([]);
  });

  /* ─── Computed: getSnapshotById ──────────────────────────── */

  it('finds a snapshot by ID across all files', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts', content: 'unique-content' }));
    const targetId = useLocalHistoryStore.getState().snapshots['a.ts'][0].id;

    const found = useLocalHistoryStore.getState().getSnapshotById(targetId);
    expect(found).not.toBeNull();
    expect(found!.content).toBe('unique-content');
  });

  it('returns null for null/undefined ID', () => {
    expect(useLocalHistoryStore.getState().getSnapshotById(null)).toBeNull();
    expect(useLocalHistoryStore.getState().getSnapshotById(undefined as any)).toBeNull();
  });

  it('returns null for non-existent ID', () => {
    expect(useLocalHistoryStore.getState().getSnapshotById('non-existent')).toBeNull();
  });

  /* ─── trimSnapshots Edge Cases ─────────────────────────── */

  it('trims to maxPerFile when adding more snapshots than limit', () => {
    useLocalHistoryStore.getState().setMaxSnapshotsPerFile(10);
    for (let i = 0; i < 15; i++) {
      useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: `v${i}` }));
    }

    expect(useLocalHistoryStore.getState().snapshots['test.ts']).toHaveLength(10);
  });

  it('keeps newer snapshots when trimming (reverse order check)', () => {
    useLocalHistoryStore.getState().setMaxSnapshotsPerFile(5);
    vi.useFakeTimers();
    // Add 8 total snapshots (only 5 should remain after trim)
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: 'first' }));
    for (let i = 1; i < 8; i++) {
      vi.advanceTimersByTime(10);
      useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ content: `v${i}` }));
    }
    vi.useRealTimers();

    const snaps = useLocalHistoryStore.getState().snapshots['test.ts']!;
    expect(snaps).toHaveLength(5);
    // newest 5 should be: v7, v6, v5, v4, v3
    expect(snaps.some(s => s.content === 'v7')).toBe(true);
    expect(snaps.some(s => s.content === 'v3')).toBe(true);
    // oldest 3 should be removed: first, v1, v2
    expect(snaps.some(s => s.content === 'first')).toBe(false);
    expect(snaps.some(s => s.content === 'v1')).toBe(false);
    expect(snaps.some(s => s.content === 'v2')).toBe(false);
  });

  /* ─── setMaxSnapshotsPerFile Edge Cases ────────────────── */

  it('persists max setting to localStorage', () => {
    const setItemSpy = vi.spyOn(window.localStorage, 'setItem');

    useLocalHistoryStore.getState().setMaxSnapshotsPerFile(10);

    expect(setItemSpy).toHaveBeenCalledWith('agk_history_max', '10');
    setItemSpy.mockRestore();
  });

  /* ─── clearFileHistory Edge Cases ──────────────────────── */

  it('keeps selectedFile when clearing a different file', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts' }));
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'b.ts', fileName: 'b.ts' }));
    useLocalHistoryStore.getState().setSelectedFile('a.ts');

    useLocalHistoryStore.getState().clearFileHistory('b.ts');

    expect(useLocalHistoryStore.getState().selectedFile).toBe('a.ts');
  });

  it('resets compareIds when clearing file history', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot());
    useLocalHistoryStore.getState().setComparePair('id-a', 'id-b');

    useLocalHistoryStore.getState().clearFileHistory('test.ts');

    expect(useLocalHistoryStore.getState().compareIds).toEqual([null, null]);
  });

  /* ─── removeSnapshot Edge Cases ────────────────────────── */

  it('does not throw when removing from non-existent file', () => {
    expect(() => {
      useLocalHistoryStore.getState().removeSnapshot('nonexistent.ts', 'some-id');
    }).not.toThrow();
  });

  /* ─── getAllFiles Edge Cases ───────────────────────────── */

  it('extracts fileName from deep paths', () => {
    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({
      filePath: 'src/utils/helpers/deep-file.ts',
      fileName: 'deep-file.ts',
    }));

    const files = useLocalHistoryStore.getState().getAllFiles();
    expect(files).toHaveLength(1);
    expect(files[0].fileName).toBe('deep-file.ts');
    expect(files[0].filePath).toBe('src/utils/helpers/deep-file.ts');
  });

  it('skips file entries with zero snapshots', () => {
    // Directly set an empty array entry
    useLocalHistoryStore.setState(prev => ({
      snapshots: { ...prev.snapshots, 'empty.ts': [] },
    }));

    useLocalHistoryStore.getState().addSnapshot(makeSnapshot({ filePath: 'a.ts', fileName: 'a.ts' }));

    const files = useLocalHistoryStore.getState().getAllFiles();
    expect(files).toHaveLength(1);
    expect(files[0].filePath).toBe('a.ts');
  });

  /* ─── clearAllHistory localStorage ─────────────────────── */

  it('removes history from localStorage on clearAllHistory', () => {
    const removeItemSpy = vi.spyOn(window.localStorage, 'removeItem');

    useLocalHistoryStore.getState().addSnapshot(makeSnapshot());
    useLocalHistoryStore.getState().clearAllHistory();

    expect(removeItemSpy).toHaveBeenCalledWith('agk_local_history');
    removeItemSpy.mockRestore();
  });

  /* ─── global MAX_TOTAL_SNAPSHOTS trim ──────────────────── */

  it('trims snapshots exceeding MAX_TOTAL_SNAPSHOTS across files', () => {
    // Create 10 files with 210 snapshots each to exceed MAX_TOTAL_SNAPSHOTS (2000)
    for (let f = 0; f < 10; f++) {
      for (let s = 0; s < 210; s++) {
        useLocalHistoryStore.getState().addSnapshot(makeSnapshot({
          filePath: `file-${f}.ts`,
          fileName: `file-${f}.ts`,
          content: `v${s}`,
        }));
      }
    }

    const state = useLocalHistoryStore.getState();
    const totalSnaps = Object.values(state.snapshots).reduce(
      (sum, arr) => sum + arr.length, 0
    );
    // Should be capped at MAX_TOTAL_SNAPSHOTS (2000)
    expect(totalSnaps).toBeLessThanOrEqual(2000);
  });

  it('preserves newest snapshots during global trim', () => {
    // Use fake timers for distinct timestamps so newest are predictable
    vi.useFakeTimers();
    // Add 3 files with 700 snaps each = 2100 total (exceeds 2000)
    for (let f = 0; f < 3; f++) {
      for (let s = 0; s < 700; s++) {
        vi.advanceTimersByTime(1);
        useLocalHistoryStore.getState().addSnapshot(makeSnapshot({
          filePath: `file-${f}.ts`,
          fileName: `file-${f}.ts`,
          content: `v${s}`,
        }));
      }
    }
    vi.useRealTimers();

    const state = useLocalHistoryStore.getState();
    const totalSnaps = Object.values(state.snapshots).reduce(
      (sum, arr) => sum + arr.length, 0
    );
    expect(totalSnaps).toBeLessThanOrEqual(2000);
  });
});
