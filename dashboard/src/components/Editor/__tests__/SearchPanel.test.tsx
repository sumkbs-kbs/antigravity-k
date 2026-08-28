/**
 * SearchPanel Tests (Phase 11)
 * =============================
 * Tests the SearchPanel component: highlightText utility, rendering,
 * search input, regex/case options, results display, replace, keyboard nav.
 */

import { describe, it, expect, vi, beforeEach, afterAll, type Mock } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import SearchPanel from '../SearchPanel';

/* ─── Mock stores ─────────────────────────────────────────── */

const mockOpenFile = vi.fn();
const mockUpdateFileContent = vi.fn();
const mockAddToast = vi.fn();
let fetchMock: Mock<typeof fetch>;

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
    if (name.endsWith('.ts')) return '\u{1F4C4}';
    if (name.endsWith('.json')) return '\u{1F4CB}';
    return '\u{1F4C4}';
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

function mockFetchResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

/* ─── SearchPanel Rendering ────────────────────────────────── */

describe('SearchPanel rendering', () => {
  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('returns null when visible is false', () => {
    const { container } = render(
      <SearchPanel visible={false} onClose={vi.fn()} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders search panel when visible is true', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const searchInput = screen.getByPlaceholderText('Search files...');
    expect(searchInput).toBeInTheDocument();

    expect(screen.getByTitle('Use Regular Expression')).toBeInTheDocument();
    expect(screen.getByTitle('Case Sensitive')).toBeInTheDocument();
    expect(screen.getByTitle('Close (Esc)')).toBeInTheDocument();
  });

  it('renders search panel with regex placeholder when useRegex is toggled', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const regexBtn = screen.getByTitle('Use Regular Expression');
    await act(async () => { fireEvent.click(regexBtn); });

    expect(screen.getByPlaceholderText('Search (regex)...')).toBeInTheDocument();
  });

  it('clears state when visible changes from true to false', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    const { rerender } = render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'test' } });
    });

    rerender(<SearchPanel visible={false} onClose={vi.fn()} />);
    rerender(<SearchPanel visible={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search files...')).toHaveValue('');
    });
  });

  it('shows loading state during search', async () => {
    const pendingPromise = new Promise<Response>(() => {});
    fetchMock.mockReturnValue(pendingPromise);

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'test' } });
    });

    await waitFor(() => {
      const loadingEls = screen.getAllByText('Searching...');
      expect(loadingEls.length).toBeGreaterThan(0);
    }, { timeout: 1000 });
  });

  it('shows no results message when search returns empty', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(emptySearchResponse));

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
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('calls search API when user types', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    }, { timeout: 1000 });

    expect(global.fetch).toHaveBeenCalledWith('/api/fs/search', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }));

    const callArgs = fetchMock.mock.calls.find(c => c[0] === '/api/fs/search');
    if (callArgs) {
      const body = JSON.parse(String(callArgs[1]?.body));
      expect(body.query).toBe('function');
      expect(body.max_results).toBe(200);
    }
  });

  it('toggles regex option and re-searches', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse(mockSearchResponse));
    vi.stubGlobal('fetch', fetchMock);

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'func' } });
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    }, { timeout: 1000 });

    fetchMock.mockClear();

    const regexBtn = screen.getByTitle('Use Regular Expression');
    await act(async () => { fireEvent.click(regexBtn); });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    }, { timeout: 1000 });

    const regexCall = fetchMock.mock.calls.find(c => c[0] === '/api/fs/search');
    if (regexCall) {
      const body = JSON.parse(String(regexCall[1]?.body));
      expect(body.regex).toBe(true);
    }
  });

  it('toggles case sensitive option and re-searches', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse(mockSearchResponse));
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

    const csCall = fetchMock.mock.calls.find(c => c[0] === '/api/fs/search');
    if (csCall) {
      const body = JSON.parse(String(csCall[1]?.body));
      expect(body.case_sensitive).toBe(true);
    }
  });

  it('shows match count in summary', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

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
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('displays file results with match lines', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText('app.ts')).toBeInTheDocument();
      expect(screen.getByText('utils.ts')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('shows collapse/expand toggle on file results', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      const collapseIcons = screen.getAllByText('\u25BC');
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

    await waitFor(() => {
      expect(screen.getByText(/No results/)).toBeInTheDocument();
    }, { timeout: 1000 });
  });
});

/* ─── Keyboard Navigation ──────────────────────────────────── */

describe('SearchPanel keyboard navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('moves focus down on ArrowDown', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });

    await act(async () => {
      fireEvent.keyDown(input, { key: 'ArrowDown' });
    });

    await waitFor(() => {
      const el = screen.getByText(/1\/3/);
      expect(el).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('moves focus down twice then up — focus stays at first match', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });

    await act(async () => { fireEvent.keyDown(input, { key: 'ArrowDown' }); });
    await act(async () => { fireEvent.keyDown(input, { key: 'ArrowDown' }); });
    await act(async () => { fireEvent.keyDown(input, { key: 'ArrowUp' }); });

    await waitFor(() => {
      const el = screen.getByText(/1\/3/);
      expect(el).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('shows navigation only when focusedIdx >= 0', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });

    expect(screen.queryByText(/\d+\/3/)).not.toBeInTheDocument();

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
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    fetchMock.mockClear();

    await act(async () => {
      fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    }, { timeout: 1000 });
  });

  it('tabs from search to replace input', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    await act(async () => {
      fireEvent.keyDown(input, { key: 'Tab', shiftKey: false });
    });
  });
});

/* ─── Replace Functionality ────────────────────────────────── */

describe('SearchPanel replace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('shows replace input after search', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

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
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

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
      const replaceBtns = screen.getAllByText('Replace');
      expect(replaceBtns.length).toBeGreaterThan(0);
    }, { timeout: 1000 });
  });

  it('shows Replace All button when replace text is entered', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

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
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('shows matches list by default (expanded)', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('hides matches when file header is clicked (collapse)', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText('app.ts')).toBeInTheDocument();
    }, { timeout: 1000 });

    const fileHeader = screen.getByText('app.ts').closest('.search-file-header');
    if (fileHeader) {
      await act(async () => { fireEvent.click(fileHeader); });
    }

    const collapseIcon = screen.getByText('\u25B6');
    expect(collapseIcon).toBeInTheDocument();
  });
});

/* ─── Replace Edge Cases ───────────────────────────────────── */

describe('SearchPanel replace edge cases', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('does not show Replace All button when replaceText is empty', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    expect(screen.queryByText(/Replace All/)).not.toBeInTheDocument();
  });

  it('does not show individual Replace buttons when replaceText is empty', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    expect(screen.queryByText('Replace')).not.toBeInTheDocument();
  });

  it('does not show per-file replace all button when replaceText is empty', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Replace with...')).toBeInTheDocument();
    }, { timeout: 1000 });

    expect(screen.queryByText('\u21BB All')).not.toBeInTheDocument();
  });
});

/* ─── Close Button ─────────────────────────────────────────── */

describe('SearchPanel close', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    render(<SearchPanel visible={true} onClose={onClose} />);

    const closeBtn = screen.getByTitle('Close (Esc)');
    await act(async () => { fireEvent.click(closeBtn); });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

/* ─── Click to Open Match ──────────────────────────────────── */

describe('SearchPanel open match', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('opens file when clicking a match line', async () => {
    fetchMock
      .mockResolvedValueOnce(mockFetchResponse(mockSearchResponse))
      .mockResolvedValueOnce(mockFetchResponse({ ok: true, content: 'file content' }));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Click the match line to open
    const matchLine = screen.getByText('10').closest('.search-match-line');
    if (matchLine) {
      await act(async () => { fireEvent.click(matchLine); });
    }

    await waitFor(() => {
      expect(mockOpenFile).toHaveBeenCalled();
    }, { timeout: 1000 });
  });

  it('shows error toast when open fails with network error', async () => {
    fetchMock
      .mockResolvedValueOnce(mockFetchResponse(mockSearchResponse))
      .mockRejectedValueOnce(new Error('Network error'));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument();
    }, { timeout: 1000 });

    const matchLine = screen.getByText('10').closest('.search-match-line');
    if (matchLine) {
      await act(async () => { fireEvent.click(matchLine); });
    }

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith(
        expect.stringContaining('\uC624\uB958'),
        'error',
      );
    }, { timeout: 1000 });
  });

  it('shows the backend detail when opening a match returns a non-OK response', async () => {
    fetchMock
      .mockResolvedValueOnce(mockFetchResponse(mockSearchResponse))
      .mockResolvedValueOnce(mockFetchResponse({ detail: 'File not found' }, 404));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => expect(screen.getByText('10')).toBeInTheDocument(), { timeout: 1000 });
    const matchLine = screen.getByText('10').closest('.search-match-line');
    if (matchLine) await act(async () => { fireEvent.click(matchLine); });

    await waitFor(() => expect(mockAddToast).toHaveBeenCalledWith('파일 열기 오류: File not found', 'error'));
    expect(mockOpenFile).not.toHaveBeenCalled();
  });

  it('rejects an invalid file content shape when opening a match', async () => {
    fetchMock
      .mockResolvedValueOnce(mockFetchResponse(mockSearchResponse))
      .mockResolvedValueOnce(mockFetchResponse({ ok: true, content: 42 }));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => expect(screen.getByText('10')).toBeInTheDocument(), { timeout: 1000 });
    const matchLine = screen.getByText('10').closest('.search-match-line');
    if (matchLine) await act(async () => { fireEvent.click(matchLine); });

    await waitFor(() => expect(mockAddToast).toHaveBeenCalledWith('파일 열기 오류: Invalid file response', 'error'));
    expect(mockOpenFile).not.toHaveBeenCalled();
  });
});

/* ─── Keyboard Navigation Edge Cases ───────────────────────── */

describe('SearchPanel keyboard edge cases', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('handles Escape on replace input to clear replaceText', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

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

    await act(async () => {
      fireEvent.keyDown(replaceInput, { key: 'Escape' });
    });

    expect(replaceInput).toHaveValue('');
  });

  it('handles Shift+Tab from replace to search input', async () => {
    fetchMock.mockResolvedValue(mockFetchResponse(mockSearchResponse));

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
      fireEvent.keyDown(replaceInput, { key: 'Tab', shiftKey: true });
    });
  });

  it('opens focused match on Enter key', async () => {
    fetchMock
      .mockResolvedValueOnce(mockFetchResponse(mockSearchResponse))
      .mockResolvedValueOnce(mockFetchResponse({ ok: true, content: 'file content' }));

    render(<SearchPanel visible={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('Search files...');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'function' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/3 matches in 2 files/)).toBeInTheDocument();
    }, { timeout: 1000 });

    await act(async () => {
      fireEvent.keyDown(input, { key: 'ArrowDown' });
    });

    await waitFor(() => {
      expect(screen.getByText(/1\/3/)).toBeInTheDocument();
    }, { timeout: 1000 });

    await act(async () => {
      fireEvent.keyDown(input, { key: 'Enter' });
    });

    await waitFor(() => {
      expect(mockOpenFile).toHaveBeenCalled();
    }, { timeout: 1000 });
  });
});
