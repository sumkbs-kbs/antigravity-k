import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import DataExtractionPage from './DataExtractionPage';

function response(payload: unknown, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 503,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

describe('DataExtractionPage', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads metrics after mount without a declaration-order failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ok: true,
      metrics: { total_calls: 42, success_rates: { overall: 95 } },
    })));

    render(<DataExtractionPage />);

    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument());
    expect(fetch).toHaveBeenCalledWith('/api/search/extraction-metrics');
  });

  it('does not parse a failed metrics response', async () => {
    const json = vi.fn().mockResolvedValue({ detail: 'unavailable' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json }));
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<DataExtractionPage />);

    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/search/extraction-metrics'));
    expect(json).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalled();
  });
});
