/**
 * editorStore Tests
 * ==================
 * Tests for the Zustand editor store — file operations, tabs, preview, save.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useEditorStore, getLanguageFromExt } from '../editorStore';

beforeEach(() => {
  // Reset store state between tests
  useEditorStore.setState({
    openFiles: [],
    activeFilePath: null,
    previewVisible: false,
    previewPath: null,
    previewTitle: '',
    previewContent: '',
  });
});

describe('getLanguageFromExt', () => {
  it('returns typescript for .ts files', () => {
    expect(getLanguageFromExt('file.ts')).toBe('typescript');
  });

  it('returns typescript for .tsx files', () => {
    expect(getLanguageFromExt('component.tsx')).toBe('typescript');
  });

  it('returns python for .py files', () => {
    expect(getLanguageFromExt('script.py')).toBe('python');
  });

  it('returns markdown for .md files', () => {
    expect(getLanguageFromExt('readme.md')).toBe('markdown');
  });

  it('returns plaintext for unknown extensions', () => {
    expect(getLanguageFromExt('unknown.xyz')).toBe('plaintext');
  });

  it('returns plaintext for files without extension', () => {
    expect(getLanguageFromExt('Makefile')).toBe('plaintext');
    expect(getLanguageFromExt('Dockerfile')).toBe('dockerfile');
  });
});

describe('useEditorStore', () => {
  /* ─── openFile ────────────────────────────────────────── */

  it('opens a new file and sets it as active', () => {
    useEditorStore.getState().openFile('src/test.ts', 'test.ts', 'console.log("hello")');

    const state = useEditorStore.getState();
    expect(state.openFiles).toHaveLength(1);
    expect(state.openFiles[0]).toMatchObject({
      path: 'src/test.ts',
      name: 'test.ts',
      content: 'console.log("hello")',
      isDirty: false,
    });
    expect(state.activeFilePath).toBe('src/test.ts');
  });

  it('does not duplicate files that are already open', () => {
    useEditorStore.getState().openFile('src/test.ts', 'test.ts', 'content');
    useEditorStore.getState().openFile('src/test.ts', 'test.ts', 'content');

    expect(useEditorStore.getState().openFiles).toHaveLength(1);
  });

  it('detects language from filename when not provided', () => {
    useEditorStore.getState().openFile('script.py', 'script.py', 'print("hi")');
    expect(useEditorStore.getState().openFiles[0].language).toBe('python');
  });

  it('accepts explicit language override', () => {
    useEditorStore.getState().openFile('script.py', 'script.py', 'print("hi")', 'go');
    expect(useEditorStore.getState().openFiles[0].language).toBe('go');
  });

  /* ─── closeFile ───────────────────────────────────────── */

  it('closes a file and removes it from openFiles', () => {
    useEditorStore.getState().openFile('a.ts', 'a.ts', 'aaa');
    useEditorStore.getState().openFile('b.ts', 'b.ts', 'bbb');

    useEditorStore.getState().closeFile('a.ts');

    expect(useEditorStore.getState().openFiles).toHaveLength(1);
    expect(useEditorStore.getState().openFiles[0].path).toBe('b.ts');
  });

  it('switches active file when closing the active file', () => {
    useEditorStore.getState().openFile('a.ts', 'a.ts', 'aaa');
    useEditorStore.getState().openFile('b.ts', 'b.ts', 'bbb');
    useEditorStore.getState().setActiveFile('a.ts');

    useEditorStore.getState().closeFile('a.ts');

    expect(useEditorStore.getState().activeFilePath).toBe('b.ts');
  });

  it('sets activeFilePath to null when closing the last file', () => {
    useEditorStore.getState().openFile('a.ts', 'a.ts', 'aaa');
    useEditorStore.getState().closeFile('a.ts');

    expect(useEditorStore.getState().activeFilePath).toBeNull();
  });

  /* ─── setActiveFile ───────────────────────────────────── */

  it('switches active file', () => {
    useEditorStore.getState().openFile('a.ts', 'a.ts', 'aaa');
    useEditorStore.getState().openFile('b.ts', 'b.ts', 'bbb');

    useEditorStore.getState().setActiveFile('b.ts');

    expect(useEditorStore.getState().activeFilePath).toBe('b.ts');
  });

  /* ─── updateFileContent ───────────────────────────────── */

  it('updates file content and marks file as dirty', () => {
    useEditorStore.getState().openFile('test.ts', 'test.ts', 'original');
    useEditorStore.getState().updateFileContent('test.ts', 'modified');

    const file = useEditorStore.getState().openFiles.find(f => f.path === 'test.ts');
    expect(file?.content).toBe('modified');
    expect(file?.isDirty).toBe(true);
  });

  it('does not modify other files when updating one file', () => {
    useEditorStore.getState().openFile('a.ts', 'a.ts', 'aaa');
    useEditorStore.getState().openFile('b.ts', 'b.ts', 'bbb');

    useEditorStore.getState().updateFileContent('a.ts', 'modified');

    const fileB = useEditorStore.getState().openFiles.find(f => f.path === 'b.ts');
    expect(fileB?.content).toBe('bbb');
    expect(fileB?.isDirty).toBe(false);
  });

  /* ─── markFileSaved ───────────────────────────────────── */

  it('marks a dirty file as saved', () => {
    useEditorStore.getState().openFile('test.ts', 'test.ts', 'original');
    useEditorStore.getState().updateFileContent('test.ts', 'modified');
    useEditorStore.getState().markFileSaved('test.ts');

    const file = useEditorStore.getState().openFiles.find(f => f.path === 'test.ts');
    expect(file?.isDirty).toBe(false);
    expect(file?.content).toBe('modified'); // content preserved
  });

  /* ─── saveFile (API call) ─────────────────────────────── */

  it('saveFile returns true for non-dirty files (no network call)', async () => {
    useEditorStore.getState().openFile('test.ts', 'test.ts', 'content');
    const result = await useEditorStore.getState().saveFile('test.ts');
    expect(result).toBe(true);
  });

  it('saveFile returns false on API failure', async () => {
    // Mock fetch to return failure
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: false }),
    });

    useEditorStore.getState().openFile('test.ts', 'test.ts', 'content');
    useEditorStore.getState().updateFileContent('test.ts', 'modified');
    const result = await useEditorStore.getState().saveFile('test.ts');

    expect(result).toBe(false);
    // Should NOT clear dirty flag on failure
    const file = useEditorStore.getState().openFiles.find(f => f.path === 'test.ts');
    expect(file?.isDirty).toBe(true);

    vi.restoreAllMocks();
  });

  /* ─── Preview ─────────────────────────────────────────── */

  it('shows preview with path, title, and content', () => {
    useEditorStore.getState().showPreview('preview.html', 'Preview', '<h1>Hello</h1>');

    const state = useEditorStore.getState();
    expect(state.previewVisible).toBe(true);
    expect(state.previewPath).toBe('preview.html');
    expect(state.previewTitle).toBe('Preview');
    expect(state.previewContent).toBe('<h1>Hello</h1>');
  });

  it('hides preview and resets state', () => {
    useEditorStore.getState().showPreview('p.html', 'P', 'content');
    useEditorStore.getState().hidePreview();

    const state = useEditorStore.getState();
    expect(state.previewVisible).toBe(false);
    expect(state.previewPath).toBeNull();
    expect(state.previewTitle).toBe('');
    expect(state.previewContent).toBe('');
  });
});
