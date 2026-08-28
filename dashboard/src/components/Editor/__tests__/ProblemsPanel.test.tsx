import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ProblemsPanel from '../ProblemsPanel';

const mockOpenFile = vi.fn();
const mockAddToast = vi.fn();
const mockSetFilterSeverity = vi.fn();
const mockSetFilterText = vi.fn();
const mockSetProblemsPanelVisible = vi.fn();
const mockProblemsState = {
  problems: [{
    id: 'problem-1',
    filePath: 'src/example.ts',
    fileName: 'example.ts',
    message: 'Type error',
    severity: 'error' as const,
    line: 3,
    column: 5,
  }],
  activeFilePath: null,
  filterSeverity: 'all' as const,
  filterText: '',
  problemsPanelVisible: true,
  setFilterSeverity: mockSetFilterSeverity,
  setFilterText: mockSetFilterText,
  setProblemsPanelVisible: mockSetProblemsPanelVisible,
  errorCount: () => 1,
  warningCount: () => 0,
  infoCount: () => 0,
};
let fetchMock: Mock<typeof fetch>;

vi.mock('../../../stores/problemsStore', () => ({
  useProblemsStore: () => mockProblemsState,
  getFilteredProblems: (problems: typeof mockProblemsState.problems) => problems,
}));

vi.mock('../../../stores/editorStore', () => ({
  useEditorStore: () => ({ openFile: mockOpenFile }),
}));

vi.mock('../../../stores/uiStore', () => ({
  useUiStore: () => ({ addToast: mockAddToast }),
}));

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('ProblemsPanel file opening', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.localStorage.setItem('ag_access_pin', 'operator-secret');
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('opens a file with the stored PIN and string content', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, content: 'const value = 1;' }));

    render(<ProblemsPanel />);
    fireEvent.click(screen.getByRole('button', { name: /Type error/ }));

    await waitFor(() => expect(mockOpenFile).toHaveBeenCalledWith(
      'src/example.ts',
      'example.ts',
      'const value = 1;',
    ));
    const request = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(request?.headers).get('X-Access-Pin')).toBe('operator-secret');
  });

  it('shows the backend detail for a non-OK response without opening the file', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'File not found' }, 404));

    render(<ProblemsPanel />);
    fireEvent.click(screen.getByRole('button', { name: /Type error/ }));

    await waitFor(() => expect(mockAddToast).toHaveBeenCalledWith('파일 열기 오류: File not found', 'error'));
    expect(mockOpenFile).not.toHaveBeenCalled();
  });

  it('rejects a successful response with an invalid content shape', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, content: 42 }));

    render(<ProblemsPanel />);
    fireEvent.click(screen.getByRole('button', { name: /Type error/ }));

    await waitFor(() => expect(mockAddToast).toHaveBeenCalledWith('파일 열기 오류: 알 수 없는 오류', 'error'));
    expect(mockOpenFile).not.toHaveBeenCalled();
  });
});
