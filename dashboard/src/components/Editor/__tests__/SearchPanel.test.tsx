/**
 * SearchPanel Tests (Phase 11)
 * =============================
 * Tests the SearchPanel component: highlightText utility, rendering,
 * search input, regex/case options, results display, replace, keyboard nav.
 */

import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import SearchPanel from '../SearchPanel';

/* ─── Mock stores ─────────────────────────────────────────── */

const mockOpenFile = vi.fn();
const mockUpdateFileContent = vi.fn();
const mockAddToast = vi.fn();

vi.mock('../../../stores/editorStore', () => ({
  useEditorStore: () => ({
    openFile: mockOpenFile,
    updateFileContent: mockUpdateFileContent,
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
    if (name.endsWith('.json')) return '📋';
    return '📄';
  },
}));

/* ─── Search Result Fixtures ───────────────────────────────── */

const mockSearchResponse = {
  ok: true,
  query: 'function',
  results: [
    {
      file_path: '/src/app.ts',
      file_name: 'app.ts',
      match_count: 2,
      matches: [
        { line: 10, content: '  function hello() {' },
        { line: 25, content: '  const foo = function() {}' },
      ],
    },
    {
      file_path: '/src/utils.ts',
      file_name: 'utils.ts',
      match_count: 1,
      matches: [
        { line: 5, content: 'export function add(a, b) {' },
      ],
    },
  ],
  total_files: 2,
  total_matches: 3,
};

const emptySearchResponse = {
  ok: true,
  query: 'zzzznotfound',
  results: [],
  total_files: 0,
  total_matches: 0,
};

/* ─── SearchPanel Rendering ────────────────────────────────── */

describe('SearchPanel rendering', () => {
  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('returns null when visible is false', () => {
    const { container } = render(
      <SearchPanel visible={false} onClose={vi.fn()} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders search panel when visible is true', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    // Should show search input
    const searchInput = screen.getByPlaceholderText('Search files...');
    expect(searchInput).toBeInTheDocument();

    // Should show option buttons
    expect(screen.getByTitle('Use Regular Expression')).toBeInTheDocument();
    expect(screen.getByTitle('Case Sensitive')).toBeInTheDocument();
    expect(screen.getByTitle('Close (Esc)')).toBeInTheDocument();
  });

  it('renders search panel with regex placeholder when useRegex is toggled', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    // Toggle regex
    const regexBtn = screen.getByTitle('Use Regular Expression');
    await act(async () => { fireEvent.click(regexBtn); });

    expect(screen.getByPlaceholderText('Search (regex)...')).toBeInTheDocument();
  });

  it('clears state when visible changes from true to false', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    const { rerender } = render(<SearchPanel visible={true} onClose={vi.fn()} />);

    // Type a query
    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'test' } });
    });

    // Re-render with visible=false
    rerender(<SearchPanel visible={false} onClose={vi.fn()} />);

    // Re-render with visible=true — should be clean
    rerender(<SearchPanel visible={true} onClose={vi.fn()} />);

    const searchInput = screen.getByPlaceholderText('Search files...');
    expect(searchInput).toHaveValue('');
  });

  it('shows loading state during search', async () => {
    // Create a promise that never resolves to keep loading state
    const pendingPromise = new Promise(() => {});
    (global.fetch as any).mockReturnValue(pendingPromise);

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'test' } });
    });

    // Wait for debounce + fetch — Searching... appears in both summary and results list
    await waitFor(() => {
      const loadingEls = screen.getAllByText('Searching...');
      expect(loadingEls.length).toBeGreaterThan(0);
    }, { timeout: 1000 });
  });

  it('shows no results message when search returns empty', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(emptySearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'zzzznotfound' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/No files found matching/)).toBeInTheDocument();
      expect(screen.getByText(/zzzznotfound/)).toBeInTheDocument();
    }, { timeout: 1000 });
  });
});

/* ─── Search Input Behavior ─────────────────────────────────── */

describe('SearchPanel search input', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('calls search API when user types', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    // Wait for debounce (300ms) + fetch
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    }, { timeout: 1000 });

    // Verify the API call
    expect(global.fetch).toHaveBeenCalledWith('/api/fs/search', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }));

    // Verify request body
    const callArgs = (global.fetch as any).mock.calls.find(
      (c: any[]) => c[0] === '/api/fs/search'
    );
    if (callArgs) {
      const body = JSON.parse(callArgs[1].body);
      expect(body.query).toBe('function');
      expect(body.max_results).toBe(200);
    }
  });

  it('toggles regex option and re-searches', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    // Type query
    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'func' } });
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    }, { timeout: 1000 });

    fetchMock.mockClear();

    // Toggle regex
    const regexBtn = screen.getByTitle('Use Regular Expression');
    await act(async () => { fireEvent.click(regexBtn); });

    // Should re-search with regex=true
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    }, { timeout: 1000 });

    const regexCall = fetchMock.mock.calls.find((c: any[]) => c[0] === '/api/fs/search');
    if (regexCall) {
      const body = JSON.parse(regexCall[1].body);
      expect(body.regex).toBe(true);
    }
  });

  it('toggles case sensitive option and re-searches', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'func' } });
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    }, { timeout: 1000 });

    fetchMock.mockClear();

    const csBtn = screen.getByTitle('Case Sensitive');
    await act(async () => { fireEvent.click(csBtn); });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    }, { timeout: 1000 });

    const csCall = fetchMock.mock.calls.find((c: any[]) => c[0] === '/api/fs/search');
    if (csCall) {
      const body = JSON.parse(csCall[1].body);
      expect(body.case_sensitive).toBe(true);
    }
  });

  it('shows match count in summary', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });
  });
});

/* ─── Search Results Display ───────────────────────────────── */

describe('SearchPanel search results', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('displays file results with match lines', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText('app.ts')).toBeInTheDocument();
      expect(screen.getByText('utils.ts')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument(); // line number
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('shows collapse/expand toggle on file results', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      // Should show collapse icon ▼ by default (expanded) — one per file group
      const collapseIcons = screen.getAllByText('▼');
      expect(collapseIcons.length).toBeGreaterThanOrEqual(1);
    }, { timeout: 1000 });
  });

  it('toggles invalid regex state gracefully', async () => {
    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const regexBtn = screen.getByTitle('Use Regular Expression');
    await act(async () => { fireEvent.click(regexBtn); });

    const input = screen.getByPlaceholderText('Search (regex)...');
    await act(async () => {
      fireEvent.change(input, { target: { value: '[invalid' } });
    });

    // Wait for debounce
    await waitFor(() => {
      expect(screen.getByText(/No results/)).toBeInTheDocument();
    }, { timeout: 1000 });
  });
});

/* ─── Keyboard Navigation ──────────────────────────────────── */

describe('SearchPanel keyboard navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('moves focus down on ArrowDown', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });

    // Press ArrowDown — focusedIdx becomes 0 (first match)
    await act(async () => {
      fireEvent.keyDown(input, { key: 'ArrowDown' });
    });

    // Navigation counter should show 1/3 (0-indexed focusedIdx=0 → display 1)
    await waitFor(() => {
      const el = screen.getByText(/1\/3/);
      expect(el).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('moves focus down twice then up — focus stays at first match', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });

    // ArrowDown (focusedIdx=0), ArrowDown (focusedIdx=1), ArrowUp (focusedIdx=0)
    await act(async () => { fireEvent.keyDown(input, { key: 'ArrowDown' }); });
    await act(async () => { fireEvent.keyDown(input, { key: 'ArrowDown' }); });
    await act(async () => { fireEvent.keyDown(input, { key: 'ArrowUp' }); });

    // After: focusedIdx=0 → display "1/3"
    await waitFor(() => {
      const el = screen.getByText(/1\/3/);
      expect(el).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('shows navigation only when focusedIdx >= 0 (kills EqualityOperator mutant)', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });

    // Initially focusedIdx=-1, so navigation counter should NOT appear
    expect(screen.queryByText(/\d+\/3/)).not.toBeInTheDocument();

    // Press ArrowDown — focusedIdx becomes 0, navigation should appear
    await act(async () => {
      fireEvent.keyDown(input, { key: 'ArrowDown' });
    });

    await waitFor(() => {
      expect(screen.getByText(/1\/3/)).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('closes panel on Escape when query is empty', async () => {
    const onClose = vi.fn();
    render(<SearchPanel visible={true} onClose={onClose} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.keyDown(input, { key: 'Escape' });
    });

    expect(onClose).toHaveBeenCalled();
  });

  it('clears query on Escape when query is non-empty', async () => {
    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'test' } });
    });
    await act(async () => {
      fireEvent.keyDown(input, { key: 'Escape' });
    });

    expect(input).toHaveValue('');
  });

  it('triggers search on Shift+Enter', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    // Clear debounce calls
    (global.fetch as any).mockClear();

    // Shift+Enter triggers immediate search
    await act(async () => {
      fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    }, { timeout: 1000 });
  });

  it('tabs from search to replace input', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Tab to replace input — just verify no crash
    await act(async () => {
      fireEvent.keyDown(input, { key: 'Tab', shiftKey: false });
    });
  });
});

/* ─── Replace Functionality ────────────────────────────────── */

describe('SearchPanel replace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('shows replace input after search', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('shows Replace button per match when replace text is entered', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    const replaceInput = screen.getByPlaceholderText('Replace with...');
    await act(async () => {
      fireEvent.change(replaceInput, { target: { value: 'fn' } });
    });

    // Replace buttons should appear
    await waitFor(() => {
      const replaceBtns = screen.getAllByText('Replace');
      expect(replaceBtns.length).toBeGreaterThan(0);
    }, { timeout: 1000 });
  });

  it('shows Replace All button when replace text is entered', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    const replaceInput = screen.getByPlaceholderText('Replace with...');
    await act(async () => {
      fireEvent.change(replaceInput, { target: { value: 'fn' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/Replace All/)).toBeInTheDocument();
    }, { timeout: 1000 });
  });
});

/* ─── FileResult Expand/Collapse ──────────────────────────── */

describe('FileResult expand/collapse', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('shows matches list by default (expanded)', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      // Matches should be visible (expanded state)
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('hides matches when file header is clicked (collapse)', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText('app.ts')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Click the file header to collapse
    const fileHeader = screen.getByText('app.ts').closest('.search-file-header');
    if (fileHeader) {
      await act(async () => { fireEvent.click(fileHeader); });
    }

    // After collapse, the ▼ icon should become ▶
    const collapseIcon = screen.getByText('▶');
    expect(collapseIcon).toBeInTheDocument();
  });
});

/* ─── Replace Edge Cases ───────────────────────────────────── */

describe('SearchPanel replace edge cases', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('does not show Replace All button when replaceText is empty', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Replace All button should NOT be visible when replaceText is empty
    expect(screen.queryByText(/Replace All/)).not.toBeInTheDocument();
  });

  it('does not show individual Replace buttons when replaceText is empty', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Individual Replace buttons should NOT be visible
    expect(screen.queryByText('Replace')).not.toBeInTheDocument();
  });

  it('does not show ↻ All per-file replace button when replaceText is empty', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve(mockSearchResponse),
    });

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    expect(screen.queryByText('↻ All')).not.toBeInTheDocument();
  });
});

/* ─── Close Button ─────────────────────────────────────────── */

describe('SearchPanel close', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    render(<SearchPanel visible={true} onClose={onClose} />);

    const closeBtn = screen.getByTitle('Close (Esc)');
    await act(async () => { fireEvent.click(closeBtn); });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
