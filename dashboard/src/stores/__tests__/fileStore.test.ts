/**
 * fileStore Tests
 * ================
 * Tests for the Zustand file store — tree data, workspace, folder/file CRUD.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useFileStore } from '../fileStore';

beforeEach(() => {
  useFileStore.setState({
    treeData: [],
    isLoading: false,
    workspacePath: '/',
    expandedPaths: new Set(),
  });
});

describe('useFileStore', () => {
  /* ─── State Setters ────────────────────────────────────── */

  it('sets tree data', () => {
    const items = [{ name: 'src', path: 'src', is_dir: true }];
    useFileStore.getState().setTreeData(items);
    expect(useFileStore.getState().treeData).toEqual(items);
  });

  it('sets loading state', () => {
    useFileStore.getState().setLoading(true);
    expect(useFileStore.getState().isLoading).toBe(true);
  });

  it('sets workspace path', () => {
    useFileStore.getState().setWorkspacePath('/home/project');
    expect(useFileStore.getState().workspacePath).toBe('/home/project');
  });

  /* ─── Expanded Paths ───────────────────────────────────── */

  it('toggles a path to expanded', () => {
    useFileStore.getState().toggleExpanded('src');
    expect(useFileStore.getState().isExpanded('src')).toBe(true);
  });

  it('toggles an expanded path back to collapsed', () => {
    useFileStore.getState().toggleExpanded('src');
    useFileStore.getState().toggleExpanded('src');
    expect(useFileStore.getState().isExpanded('src')).toBe(false);
  });

  it('returns false for never-expanded paths', () => {
    expect(useFileStore.getState().isExpanded('nonexistent')).toBe(false);
  });

  it('supports multiple expanded paths independently', () => {
    useFileStore.getState().toggleExpanded('a');
    useFileStore.getState().toggleExpanded('b');
    expect(useFileStore.getState().isExpanded('a')).toBe(true);
    expect(useFileStore.getState().isExpanded('b')).toBe(true);

    useFileStore.getState().toggleExpanded('a');
    expect(useFileStore.getState().isExpanded('a')).toBe(false);
    expect(useFileStore.getState().isExpanded('b')).toBe(true);
  });

  /* ─── loadDirectory ────────────────────────────────────── */

  it('loadDirectory returns items on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({
        ok: true,
        items: [
          { name: 'src', path: 'src', is_dir: true },
          { name: 'test.ts', path: 'test.ts', is_dir: false },
        ],
      }),
    });

    const items = await useFileStore.getState().loadDirectory('.');
    expect(items).toHaveLength(2);
    expect(items[0].name).toBe('src');

    vi.restoreAllMocks();
  });

  it('loadDirectory returns empty array on API failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const items = await useFileStore.getState().loadDirectory('.');
    expect(items).toEqual([]);

    vi.restoreAllMocks();
  });

  /* ─── createFolder ─────────────────────────────────────── */

  it('createFolder returns true on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: true }),
    });

    const result = await useFileStore.getState().createFolder('new-folder');
    expect(result).toBe(true);

    vi.restoreAllMocks();
  });

  it('createFolder returns false on API failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const result = await useFileStore.getState().createFolder('new-folder');
    expect(result).toBe(false);

    vi.restoreAllMocks();
  });

  /* ─── getWorkspace ─────────────────────────────────────── */

  it('getWorkspace returns the workspace path', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: true, workspace: '/home/project' }),
    });

    const path = await useFileStore.getState().getWorkspace();
    expect(path).toBe('/home/project');
    expect(useFileStore.getState().workspacePath).toBe('/home/project');

    vi.restoreAllMocks();
  });

  it('getWorkspace returns / on API failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const path = await useFileStore.getState().getWorkspace();
    expect(path).toBe('/');
    // Should not change existing workspace path
    expect(useFileStore.getState().workspacePath).toBe('/');

    vi.restoreAllMocks();
  });

  /* ─── renamePath ───────────────────────────────────────── */

  it('renamePath returns ok on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: true }),
    });

    const result = await useFileStore.getState().renamePath('old.ts', 'new.ts');
    expect(result.ok).toBe(true);

    vi.restoreAllMocks();
  });

  it('renamePath returns error detail on API failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: false, detail: 'File already exists' }),
    });

    const result = await useFileStore.getState().renamePath('old.ts', 'new.ts');
    expect(result.ok).toBe(false);
    expect(result.detail).toBe('File already exists');

    vi.restoreAllMocks();
  });

  /* ─── deletePath ───────────────────────────────────────── */

  it('deletePath returns true on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: true }),
    });

    const result = await useFileStore.getState().deletePath('file.ts');
    expect(result).toBe(true);

    vi.restoreAllMocks();
  });

  it('deletePath returns false on API failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const result = await useFileStore.getState().deletePath('file.ts');
    expect(result).toBe(false);

    vi.restoreAllMocks();
  });

  /* ─── refreshTree ──────────────────────────────────────── */

  it('refreshTree updates treeData from workspace', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({
        ok: true,
        items: [
          { name: 'src', path: 'src', is_dir: true },
          { name: 'readme.md', path: 'readme.md', is_dir: false },
        ],
      }),
    });

    await useFileStore.getState().refreshTree();

    const state = useFileStore.getState();
    expect(state.treeData).toHaveLength(2);
    expect(state.isLoading).toBe(false);

    vi.restoreAllMocks();
  });
});
