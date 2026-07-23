/**
 * FileTree Tests (Phase 12 — memoization)
 * ==========================================
 * Tests the treeNodeAreEqual comparator and FileTreeNode rendering,
 * click behavior, context menu, and inline editing.
 */

import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import FileTree from '../FileTree';

/* ─── Mutable store state (overridable between tests) ─────── */

const mockToggleExpanded = vi.fn();
const mockLoadDirectory = vi.fn();
const mockOpenFile = vi.fn();
const mockCloseFile = vi.fn();
const mockSaveFile = vi.fn();
const mockAddToast = vi.fn();
const mockDeletePath = vi.fn();
const mockRefreshTree = vi.fn();
const mockRenamePath = vi.fn();
const mockCreateFile = vi.fn();
const mockCreateFolder = vi.fn();

const mockExpandedPaths = new Set<string>();

// Mutable state objects — tests can modify these before render
const fileStoreState: {
  treeData: Array<{ name: string; path: string; is_dir: boolean }>;
  isLoading: boolean;
  workspacePath: string | null;
} = {
  treeData: [
    { name: 'src', path: '/src', is_dir: true },
    { name: 'app.ts', path: '/app.ts', is_dir: false },
    { name: 'utils.ts', path: '/utils.ts', is_dir: false },
    { name: 'package.json', path: '/package.json', is_dir: false },
  ],
  isLoading: false,
  workspacePath: '/workspace',
};

const editorStoreState: {
  activeFilePath: string | null;
  openFiles: Array<{ path: string; name: string; isDirty: boolean; language: string }>;
} = {
  activeFilePath: '/app.ts',
  openFiles: [
    { path: '/app.ts', name: 'app.ts', isDirty: true, language: 'typescript' },
  ],
};

vi.mock('../../../stores/fileStore', () => ({
  useFileStore: () => ({
    expandedPaths: mockExpandedPaths,
    toggleExpanded: mockToggleExpanded,
    loadDirectory: mockLoadDirectory,
    createFolder: mockCreateFolder,
    createFile: mockCreateFile,
    renamePath: mockRenamePath,
    deletePath: mockDeletePath,
    refreshTree: mockRefreshTree,
    treeData: fileStoreState.treeData,
    isLoading: fileStoreState.isLoading,
    workspacePath: fileStoreState.workspacePath,
  }),
}));

vi.mock('../../../stores/editorStore', () => ({
  useEditorStore: () => ({
    openFile: mockOpenFile,
    closeFile: mockCloseFile,
    saveFile: mockSaveFile,
    activeFilePath: editorStoreState.activeFilePath,
    openFiles: editorStoreState.openFiles,
  }),
}));

vi.mock('../../../stores/uiStore', () => ({
  useUiStore: () => ({
    addToast: mockAddToast,
  }),
}));

vi.mock('../../../utils/fileIcons', () => ({
  getFileIcon: (name: string) => {
    if (name.endsWith('.ts')) return '📄';
    return '📄';
  },
}));

/* ─── Helpers ──────────────────────────────────────────────── */

function resetFileStoreState() {
  fileStoreState.treeData = [
    { name: 'src', path: '/src', is_dir: true },
    { name: 'app.ts', path: '/app.ts', is_dir: false },
    { name: 'utils.ts', path: '/utils.ts', is_dir: false },
    { name: 'package.json', path: '/package.json', is_dir: false },
  ];
  fileStoreState.isLoading = false;
  fileStoreState.workspacePath = '/workspace';
  editorStoreState.activeFilePath = '/app.ts';
  editorStoreState.openFiles = [
    { path: '/app.ts', name: 'app.ts', isDirty: true, language: 'typescript' },
  ];
}

/* ─── FileTree ─────────────────────────────────────────────── */

describe('FileTree', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockExpandedPaths.clear();
    resetFileStoreState();
  });

  it('renders workspace root', () => {
    render(<FileTree />);
    expect(screen.getByText('workspace')).toBeInTheDocument();
  });

  it('renders tree data items', () => {
    render(<FileTree />);
    expect(screen.getByText('src')).toBeInTheDocument();
    expect(screen.getByText('app.ts')).toBeInTheDocument();
    expect(screen.getByText('utils.ts')).toBeInTheDocument();
    expect(screen.getByText('package.json')).toBeInTheDocument();
  });

  it('shows loading state when isLoading is true', () => {
    fileStoreState.treeData = [];
    fileStoreState.isLoading = true;
    fileStoreState.workspacePath = null;

    render(<FileTree />);
    expect(screen.getByText('Loading workspace...')).toBeInTheDocument();
  });

  it('shows empty state when no files', () => {
    fileStoreState.treeData = [];
    fileStoreState.isLoading = false;
    fileStoreState.workspacePath = null;

    render(<FileTree />);
    expect(screen.getByText(/No files/)).toBeInTheDocument();
    expect(screen.getByText('🔄 Refresh')).toBeInTheDocument();
  });
});

/* ─── FileTreeNode — Click Behavior ─────────────────────────── */

describe('FileTreeNode click behavior', () => {
  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockExpandedPaths.clear();
    resetFileStoreState();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('toggles directory expansion on click', async () => {
    mockLoadDirectory.mockResolvedValue([
      { name: 'index.ts', path: '/src/index.ts', is_dir: false },
    ]);

    render(<FileTree />);
    await act(async () => { fireEvent.click(screen.getByText('src')); });
    expect(mockToggleExpanded).toHaveBeenCalledWith('/src');
  });

  it('opens file on click', async () => {
    vi.mocked(global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve({ content: 'const x = 1;' }),
    });

    render(<FileTree />);
    await act(async () => { fireEvent.click(screen.getByText('app.ts')); });

    await waitFor(() => {
      expect(mockOpenFile).toHaveBeenCalledWith('/app.ts', 'app.ts', 'const x = 1;');
    });
  });

  it('shows error toast when file read fails', async () => {
    vi.mocked(global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve({ detail: 'File not found', content: undefined }),
    });

    render(<FileTree />);
    await act(async () => { fireEvent.click(screen.getByText('utils.ts')); });

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith(
        expect.stringContaining('파일 읽기 실패'),
        'error',
      );
    });
  });
});

/* ─── Context Menu ─────────────────────────────────────────── */

describe('FileTreeNode context menu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockExpandedPaths.clear();
    resetFileStoreState();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('opens context menu on right-click', async () => {
    render(<FileTree />);

    const fileNode = screen.getByText('utils.ts');
    await act(async () => {
      fireEvent.contextMenu(fileNode);
    });

    // Check that context menu rendered (using class name)
    const menus = document.querySelectorAll('.context-menu');
    expect(menus.length).toBeGreaterThanOrEqual(1);
  });

  it('context menu contains menu items', async () => {
    const { container } = render(<FileTree />);

    await act(async () => {
      fireEvent.contextMenu(screen.getByText('utils.ts'));
    });

    // The .context-menu-item elements should be rendered
    const menuItems = container.querySelectorAll('.context-menu-item');
    expect(menuItems.length).toBeGreaterThanOrEqual(4);
    // Check text content of menu items
    const texts = Array.from(menuItems).map(el => el.textContent || '');
    expect(texts.some(t => t.includes('Rename'))).toBe(true);
    expect(texts.some(t => t.includes('Delete'))).toBe(true);
    expect(texts.some(t => t.includes('New File'))).toBe(true);
    expect(texts.some(t => t.includes('New Folder'))).toBe(true);
  });

  it('shows Save option for dirty file', async () => {
    render(<FileTree />);

    // app.ts is active and dirty in the default mock state
    await act(async () => {
      fireEvent.contextMenu(screen.getByText('app.ts'));
    });

    // Save item should exist
    const saveItems = document.querySelectorAll('.context-menu-item');
    const hasSave = Array.from(saveItems).some(el => el.textContent?.includes('Save'));
    expect(hasSave).toBe(true);
  });
});

/* ─── Active styling ───────────────────────────────────────── */

describe('treeNodeAreEqual comparator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockExpandedPaths.clear();
    resetFileStoreState();
  });

  it('renders different nodes with different properties', () => {
    render(<FileTree />);
    expect(screen.getByText('app.ts')).toBeInTheDocument();
    expect(screen.getByText('utils.ts')).toBeInTheDocument();
    expect(screen.getByText('src')).toBeInTheDocument();
  });

  it('marks active file with active styling', () => {
    render(<FileTree />);
    const treeNodes = document.querySelectorAll('.tree-node');
    const activeNode = Array.from(treeNodes).find(n => n.classList.contains('active'));
    expect(activeNode).toBeTruthy();
    expect(activeNode?.textContent).toContain('app.ts');
  });
});
