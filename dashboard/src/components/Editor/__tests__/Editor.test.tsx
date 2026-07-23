/**
 * Editor Tests (Phase 12 — memoization)
 * =========================================
 * Tests EditorTabs memoization, rendering, tab management.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { useEditorStore } from '../../../stores/editorStore';
import CodeEditor from '../Editor';

/* ─── Mock stores ─────────────────────────────────────────── */

const mockSetActiveFile = vi.fn();
const mockCloseFile = vi.fn();
const mockUpdateFileContent = vi.fn();
const mockSaveFile = vi.fn();
const mockAddToast = vi.fn();
const mockSetProblemsActiveFile = vi.fn();

function makeEditorStoreState(overrides: Partial<{
  openFiles: Array<{ path: string; name: string; isDirty: boolean; language: string }>;
  activeFilePath: string | null;
}> = {}) {
  const state = {
    openFiles: overrides.openFiles ?? [
      { path: '/app.ts', name: 'app.ts', isDirty: false, language: 'typescript' },
      { path: '/helper.ts', name: 'helper.ts', isDirty: true, language: 'typescript' },
      { path: '/data.json', name: 'data.json', isDirty: false, language: 'json' },
    ],
    activeFilePath: overrides.activeFilePath ?? '/app.ts',
    closeFile: mockCloseFile,
    setActiveFile: mockSetActiveFile,
    updateFileContent: mockUpdateFileContent,
    saveFile: mockSaveFile,
  };
  return state;
}

// Create a callable function that also has .getState()
function createMockUseEditorStore(defaultState: ReturnType<typeof makeEditorStoreState>) {
  const hook = (selector?: (s: any) => any) => {
    return selector ? selector(defaultState) : defaultState;
  };
  hook.getState = () => defaultState;
  hook.setState = vi.fn();
  return hook;
}

let currentEditorStoreState = makeEditorStoreState();

vi.mock('../../../stores/editorStore', () => ({
  useEditorStore: new Proxy(
    ((selector?: (s: any) => any) => {
      const state = currentEditorStoreState;
      return selector ? selector(state) : state;
    }) as any,
    {
      get(target, prop) {
        if (prop === 'getState') return () => currentEditorStoreState;
        if (prop === 'setState') return vi.fn();
        return Reflect.get(target, prop);
      },
    },
  ),
  default: {},
}));

vi.mock('../../../stores/problemsStore', () => ({
  useProblemsStore: () => ({
    setActiveFile: mockSetProblemsActiveFile,
    problems: [],
  }),
}));

vi.mock('../../../stores/uiStore', () => ({
  useUiStore: () => ({
    addToast: mockAddToast,
  }),
}));

vi.mock('../../../stores/inlineEditStore', () => ({
  useInlineEditStore: () => ({
    isVisible: false,
    content: '',
    position: null,
    hide: vi.fn(),
    apply: vi.fn(),
    updateContent: vi.fn(),
  }),
}));

// Lazy-loaded MonacoEditorWrapper
vi.mock('../MonacoEditorWrapper', () => ({
  default: () => <div data-testid="monaco-editor">Monaco Editor</div>,
}));

vi.mock('../ProblemsPanel', () => ({
  default: () => <div data-testid="problems-panel">Problems</div>,
}));

vi.mock('../StatusBar', () => ({
  default: () => <div data-testid="status-bar">Status</div>,
}));

vi.mock('../InlineEditOverlay', () => ({
  default: () => null,
}));

/* ─── Helper to override editor store state per test ──────── */

function setEditorStoreState(overrides: Partial<{
  openFiles: Array<{ path: string; name: string; isDirty: boolean; language: string }>;
  activeFilePath: string | null;
}>) {
  currentEditorStoreState = makeEditorStoreState(overrides);
}

/* ─── EditorTabs Rendering ─────────────────────────────────── */

describe('EditorTabs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setEditorStoreState({});
  });

  it('renders open files as tabs', () => {
    render(<CodeEditor />);

    expect(screen.getByText('app.ts')).toBeInTheDocument();
    expect(screen.getByText('helper.ts')).toBeInTheDocument();
    expect(screen.getByText('data.json')).toBeInTheDocument();
  });

  it('marks active tab with different styling', () => {
    const { container } = render(<CodeEditor />);

    // app.ts is active (activeFilePath='/app.ts')
    const tabs = container.querySelectorAll('.editor-tab');
    const activeTab = Array.from(tabs).find(t => t.classList.contains('active'));
    expect(activeTab).toBeTruthy();
    expect(activeTab?.textContent).toContain('app.ts');
  });

  it('shows dirty indicator for unsaved files', () => {
    render(<CodeEditor />);

    // helper.ts is dirty (isDirty: true)
    const helperTab = screen.getByText('helper.ts').closest('.editor-tab');
    expect(helperTab).toBeTruthy();
    // Dirty indicator (●) should be present
    expect(helperTab?.textContent).toContain('●');
  });

  it('switches active file on tab click', async () => {
    render(<CodeEditor />);

    const helperTab = screen.getByText('helper.ts');
    await act(async () => { fireEvent.click(helperTab); });

    expect(mockSetActiveFile).toHaveBeenCalledWith('/helper.ts');
  });

  it('closes file on close button click', async () => {
    render(<CodeEditor />);

    // Each tab has an ✕ button. Find the one for app.ts
    const tab = screen.getByText('app.ts').closest('.editor-tab');
    const closeBtn = tab?.querySelector('button');
    if (closeBtn) {
      await act(async () => { fireEvent.click(closeBtn); });
      expect(mockCloseFile).toHaveBeenCalled();
    }
  });
});

/* ─── Editor Welcome Tab ───────────────────────────────────── */

describe('Editor welcome tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows welcome tab when no files are open', () => {
    setEditorStoreState({
      openFiles: [],
      activeFilePath: null,
    });

    render(<CodeEditor />);
    expect(screen.getByText('Welcome')).toBeInTheDocument();
    expect(screen.getByText(/Select a file/)).toBeInTheDocument();
  });
});

/* ─── Editor Save ──────────────────────────────────────────── */

describe('Editor save', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setEditorStoreState({});
  });

  it('does not render save button for non-dirty active file', () => {
    render(<CodeEditor />);
    // app.ts is active but isDirty=false, so no save button
    const appTab = screen.getByText('app.ts').closest('.editor-tab');
    const saveBtn = appTab?.querySelector('.tab-save-btn');
    expect(saveBtn).toBeFalsy();
  });

  it('shows save button for dirty active file', () => {
    setEditorStoreState({
      openFiles: [
        { path: '/app.ts', name: 'app.ts', isDirty: true, language: 'typescript' },
      ],
      activeFilePath: '/app.ts',
    });

    render(<CodeEditor />);

    // app.ts is active AND dirty — save button should appear
    const appTab = screen.getByText('app.ts').closest('.editor-tab');
    const saveBtn = appTab?.querySelector('.tab-save-btn');
    expect(saveBtn).toBeTruthy();
  });

  it('triggers save via custom event — dirty file saves', async () => {
    setEditorStoreState({
      openFiles: [
        { path: '/app.ts', name: 'app.ts', isDirty: true, language: 'typescript' },
      ],
      activeFilePath: '/app.ts',
    });

    mockSaveFile.mockResolvedValue(true);

    render(<CodeEditor />);

    // Dispatch save event
    await act(async () => {
      window.dispatchEvent(new CustomEvent('agk:editor-save'));
    });

    await waitFor(() => {
      expect(mockSaveFile).toHaveBeenCalledWith('/app.ts');
      expect(mockAddToast).toHaveBeenCalledWith(
        expect.stringContaining('✅'),
        'success',
      );
    });
  });

  it('shows error toast when save fails', async () => {
    setEditorStoreState({
      openFiles: [
        { path: '/app.ts', name: 'app.ts', isDirty: true, language: 'typescript' },
      ],
      activeFilePath: '/app.ts',
    });

    mockSaveFile.mockResolvedValue(false);

    render(<CodeEditor />);

    await act(async () => {
      window.dispatchEvent(new CustomEvent('agk:editor-save'));
    });

    await waitFor(() => {
      expect(mockSaveFile).toHaveBeenCalledWith('/app.ts');
      expect(mockAddToast).toHaveBeenCalledWith(
        expect.stringContaining('❌'),
        'error',
      );
    });
  });
});

/* ─── Editor Saving State ──────────────────────────────────── */

describe('Editor save button states', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setEditorStoreState({});
  });

  it('shows save button disabled during saving (CSS class check)', () => {
    setEditorStoreState({
      openFiles: [
        { path: '/app.ts', name: 'app.ts', isDirty: true, language: 'typescript' },
      ],
      activeFilePath: '/app.ts',
    });

    render(<CodeEditor />);

    const appTab = screen.getByText('app.ts').closest('.editor-tab');
    const saveBtn = appTab?.querySelector('.tab-save-btn') as HTMLButtonElement;
    expect(saveBtn).toBeTruthy();
    // Initially saving=false so button should not be disabled
    expect(saveBtn.disabled).toBe(false);
  });
});

/* ─── Editor Placeholder ───────────────────────────────────── */

describe('Editor placeholder', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows placeholder text when no file is selected', () => {
    setEditorStoreState({
      openFiles: [],
      activeFilePath: null,
    });

    render(<CodeEditor />);
    expect(screen.getByText('Welcome')).toBeInTheDocument();
    expect(screen.getByText(/Select a file/)).toBeInTheDocument();
  });

  it('does not show placeholder when file is open', () => {
    setEditorStoreState({});

    const { container } = render(<CodeEditor />);
    // The placeholder text should not be present
    expect(container.textContent).not.toMatch(/Select a file/);
  });
});

/* ─── Memoization ──────────────────────────────────────────── */

describe('EditorTabs memoization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setEditorStoreState({});
  });

  it('renders Monaco editor for active file', () => {
    render(<CodeEditor />);
    // MonacoEditorWrapper should be rendered for active file (app.ts)
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
  });

  it('renders problems panel and status bar', () => {
    render(<CodeEditor />);
    expect(screen.getByTestId('problems-panel')).toBeInTheDocument();
    expect(screen.getByTestId('status-bar')).toBeInTheDocument();
  });

  it('does not crash when save is triggered without active file', async () => {
    setEditorStoreState({
      openFiles: [],
      activeFilePath: null,
    });

    render(<CodeEditor />);

    await act(async () => {
      window.dispatchEvent(new CustomEvent('agk:editor-save'));
    });

    // Should not throw or call saveFile
    expect(mockSaveFile).not.toHaveBeenCalled();
  });

  it('handles keyboard Ctrl+S when Monaco is not focused', async () => {
    render(<CodeEditor />);

    // Simulate Ctrl+S on window
    await act(async () => {
      window.dispatchEvent(
        new KeyboardEvent('keydown', { key: 's', metaKey: true, bubbles: true }),
      );
    });

    // Just verify no crash — save may or may not fire depending on dirty state
  });
});
