import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  checkoutGitBranch,
  commitGit,
  createGitBranch,
  deleteGitBranch,
  fetchGitBranches,
  fetchGitDiff,
  fetchGitGraph,
  fetchGitLog,
  fetchGitStatus,
  stageGitFiles,
  unstageGitFiles,
} from '../gitApi';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const malformedResponse = {
  ok: true,
  json: () => Promise.resolve({ ok: 'yes' }),
};

const requests: ReadonlyArray<Readonly<{
  name: string;
  expectedError: string;
  run: () => Promise<unknown>;
}>> = [
  { name: 'status', expectedError: 'Invalid Git status response', run: () => fetchGitStatus('.') },
  { name: 'log', expectedError: 'Invalid Git log response', run: () => fetchGitLog('.', 20, '') },
  { name: 'branches', expectedError: 'Invalid Git branches response', run: () => fetchGitBranches('.') },
  { name: 'diff', expectedError: 'Invalid Git diff response', run: () => fetchGitDiff('', false, '.') },
  { name: 'graph', expectedError: 'Invalid Git graph response', run: () => fetchGitGraph('.', 30) },
  { name: 'stage', expectedError: 'Invalid Git stage response', run: () => stageGitFiles([], '.') },
  { name: 'unstage', expectedError: 'Invalid Git unstage response', run: () => unstageGitFiles([], '.') },
  { name: 'commit', expectedError: 'Invalid Git commit response', run: () => commitGit('message', true, '.') },
  { name: 'checkout', expectedError: 'Invalid Git checkout response', run: () => checkoutGitBranch('main', '.') },
  {
    name: 'branch create',
    expectedError: 'Invalid Git branch create response',
    run: () => createGitBranch('feature', '', '.'),
  },
  {
    name: 'branch delete',
    expectedError: 'Invalid Git branch delete response',
    run: () => deleteGitBranch('feature', false, '.'),
  },
];

beforeEach(() => {
  mockFetch.mockReset();
  mockFetch.mockResolvedValue(malformedResponse);
});

describe('Git API response validation', () => {
  it.each(requests)('rejects malformed $name responses', async ({ run, expectedError }) => {
    await expect(run()).rejects.toThrow(expectedError);
  });

  it('checks status before parsing non-OK responses and preserves API error details', async () => {
    const json = vi.fn().mockResolvedValue({ ok: true });
    mockFetch.mockResolvedValue({ ok: false, status: 503, statusText: 'Unavailable', json });

    await expect(fetchGitStatus('.')).rejects.toThrow('HTTP 503: Unavailable');
    expect(json).toHaveBeenCalledOnce();
  });
});
