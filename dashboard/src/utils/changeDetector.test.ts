import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { useChangeStore } from '../stores/changeStore';
import { detectChangesFromContent } from './changeDetector';

const fileChange = '[FILE: src/example.ts]\nconst value = 1;';
let fetchMock: Mock<typeof fetch>;

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('changeDetector file reads', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    useChangeStore.getState().clearChanges();
    window.localStorage.setItem('ag_access_pin', 'operator-secret');
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('uses the stored PIN and registers changed file content', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, content: 'const value = 0;' }));

    await expect(detectChangesFromContent(fileChange)).resolves.toBe(1);

    const request = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(request?.headers).get('X-Access-Pin')).toBe('operator-secret');
    expect(useChangeStore.getState().changes[0]?.originalContent).toBe('const value = 0;');
  });

  it('treats a missing file as new without parsing an error payload', async () => {
    const response = jsonResponse({ detail: 'File not found' }, 404);
    fetchMock.mockResolvedValue(response);

    await expect(detectChangesFromContent(fileChange)).resolves.toBe(1);

    expect(useChangeStore.getState().changes[0]?.originalContent).toBe('');
    expect(response.bodyUsed).toBe(false);
  });

  it('skips changes when the file read fails with a server error', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'workspace unavailable' }, 503));

    await expect(detectChangesFromContent(fileChange)).resolves.toBe(0);

    expect(useChangeStore.getState().changes).toHaveLength(0);
  });

  it('skips successful responses with an invalid content shape', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, content: 42 }));

    await expect(detectChangesFromContent(fileChange)).resolves.toBe(0);

    expect(useChangeStore.getState().changes).toHaveLength(0);
  });
});
