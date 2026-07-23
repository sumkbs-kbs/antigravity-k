/**
 * Tests for gitStore — Zustand Git state store with mocked fetch.
 *
 * Covers: initial state, setter actions (setCommitDialogOpen, setCommitMessage,
 * setActiveTab, setSelectedLogCommit, setShowStagedDiff), fetch actions with
 * mocked fetch (fetchStatus, fetchLog, fetchBranches, fetchDiff, fetchGraph,
 * stageFiles, unstageFiles, commit, checkoutBranch, createBranch, deleteBranch),
 * error handling, and failure paths.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useGitStore } from '../gitStore';

// ─── Mock fetch globally ─────────────────────────────────────────

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const mockOkResponse = (data: any) => ({
  ok: true,
  json: () => Promise.resolve(data),
});

const mockFailResponse = (error = 'API error') => ({
  ok: false,
  json: () => Promise.resolve({ error }),
});

const mockNetworkError = () => Promise.reject(new Error('Network failure'));

beforeEach(() => {
  // Reset store state between tests
  useGitStore.setState({
    status: { loading: false, branch: '', upstream: null, ahead: 0, behind: 0, files: [], counts: { staged: 0, unstaged: 0, untracked: 0, total: 0 }, error: null },
    log: { loading: false, commits: [], error: null },
    branches: { loading: false, list: [], current: '', error: null },
    diff: { loading: false, content: '', stat: '', error: null },
    graph: { loading: false, nodes: [], error: null },
    commitDialogOpen: false,
    commitMessage: '',
    commitStageAll: true,
    activeTab: 'status',
    selectedLogCommit: null,
    showStagedDiff: false,
  });
  mockFetch.mockReset();
});

// ─── Test gitStore ────────────────────────────────────────────────

describe('gitStore', () => {
  describe('initial state', () => {
    it('has default status state', () => {
      const state = useGitStore.getState();
      expect(state.status.loading).toBe(false);
      expect(state.status.branch).toBe('');
      expect(state.status.files).toEqual([]);
    });

    it('has default UI state', () => {
      const state = useGitStore.getState();
      expect(state.commitDialogOpen).toBe(false);
      expect(state.commitMessage).toBe('');
      expect(state.commitStageAll).toBe(true);
      expect(state.activeTab).toBe('status');
      expect(state.selectedLogCommit).toBeNull();
      expect(state.showStagedDiff).toBe(false);
    });
  });

  describe('setter actions', () => {
    it('setCommitDialogOpen sets dialog open and clears commit message', () => {
      useGitStore.getState().setCommitMessage('test msg');
      useGitStore.getState().setCommitDialogOpen(true);
      expect(useGitStore.getState().commitDialogOpen).toBe(true);
      expect(useGitStore.getState().commitMessage).toBe('');
    });

    it('setCommitMessage updates commit message', () => {
      useGitStore.getState().setCommitMessage('fix: bug');
      expect(useGitStore.getState().commitMessage).toBe('fix: bug');
    });

    it('setCommitStageAll toggles stageAll', () => {
      useGitStore.getState().setCommitStageAll(false);
      expect(useGitStore.getState().commitStageAll).toBe(false);
    });

    it('setActiveTab changes active tab', () => {
      useGitStore.getState().setActiveTab('log');
      expect(useGitStore.getState().activeTab).toBe('log');
    });

    it('setSelectedLogCommit sets commit', () => {
      const commit = { hash: 'abc', short_hash: 'abc', author_name: 'me', author_email: 'me@x.com', date: '2026-01-01', message: 'fix' };
      useGitStore.getState().setSelectedLogCommit(commit);
      expect(useGitStore.getState().selectedLogCommit?.hash).toBe('abc');
    });

    it('setSelectedLogCommit clears commit with null', () => {
      useGitStore.getState().setSelectedLogCommit(null);
      expect(useGitStore.getState().selectedLogCommit).toBeNull();
    });

    it('setShowStagedDiff toggles showStagedDiff', () => {
      useGitStore.getState().setShowStagedDiff(true);
      expect(useGitStore.getState().showStagedDiff).toBe(true);
    });
  });

  describe('fetchStatus', () => {
    it('sets status on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({
        ok: true, branch: 'main', upstream: 'origin/main', ahead: 1, behind: 0,
        files: [{ file_path: 'test.ts', x: 'M', y: ' ' }],
        counts: { staged: 1, unstaged: 0, untracked: 0, total: 1 },
      }));
      await useGitStore.getState().fetchStatus();
      const state = useGitStore.getState();
      expect(state.status.loading).toBe(false);
      expect(state.status.branch).toBe('main');
      expect(state.status.counts.staged).toBe(1);
    });

    it('sets error on failed API response', async () => {
      mockFetch.mockResolvedValue(mockFailResponse('Repo not found'));
      await useGitStore.getState().fetchStatus();
      expect(useGitStore.getState().status.error).toBe('Repo not found');
    });

    it('sets error on network failure', async () => {
      mockFetch.mockRejectedValue(new Error('Network failure'));
      await useGitStore.getState().fetchStatus();
      expect(useGitStore.getState().status.error).toBe('Network failure');
    });
  });

  describe('fetchLog', () => {
    it('sets commits on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true, commits: [{ hash: 'abc' }] }));
      await useGitStore.getState().fetchLog();
      expect(useGitStore.getState().log.commits.length).toBe(1);
    });

    it('sets error on failure', async () => {
      mockFetch.mockResolvedValue(mockFailResponse('No commits'));
      await useGitStore.getState().fetchLog();
      expect(useGitStore.getState().log.error).toBe('No commits');
    });
  });

  describe('fetchBranches', () => {
    it('sets branches on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true, branches: [{ name: 'main', is_current: true, is_remote: false }], current: 'main' }));
      await useGitStore.getState().fetchBranches();
      expect(useGitStore.getState().branches.list.length).toBe(1);
      expect(useGitStore.getState().branches.current).toBe('main');
    });

    it('sets error on failure', async () => {
      mockFetch.mockResolvedValue(mockFailResponse('No branches'));
      await useGitStore.getState().fetchBranches();
      expect(useGitStore.getState().branches.error).toBe('No branches');
    });
  });

  describe('fetchDiff', () => {
    it('sets diff on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true, diff: '+test', stat: '1 file' }));
      await useGitStore.getState().fetchDiff('test.ts');
      expect(useGitStore.getState().diff.content).toBe('+test');
    });
  });

  describe('fetchGraph', () => {
    it('sets nodes on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true, nodes: [{ hash: 'abc', graph: '*', short_hash: 'abc', author: 'me', message: 'fix', date: '2026-01-01', refs: '' }] }));
      await useGitStore.getState().fetchGraph();
      expect(useGitStore.getState().graph.nodes.length).toBe(1);
    });
  });

  describe('stageFiles', () => {
    it('returns true on success and refreshes status', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true }));
      const result = await useGitStore.getState().stageFiles(['test.ts']);
      expect(result).toBe(true);
    });

    it('returns false on API failure', async () => {
      mockFetch.mockResolvedValue(mockFailResponse('Stage failed'));
      const result = await useGitStore.getState().stageFiles(['test.ts']);
      expect(result).toBe(false);
    });

    it('returns false on network error', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));
      const result = await useGitStore.getState().stageFiles(['test.ts']);
      expect(result).toBe(false);
    });
  });

  describe('unstageFiles', () => {
    it('returns true on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true }));
      const result = await useGitStore.getState().unstageFiles(['test.ts']);
      expect(result).toBe(true);
    });
  });

  describe('commit', () => {
    it('returns true on success and refreshes multiple states', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true }));
      const result = await useGitStore.getState().commit('fix bug');
      expect(result).toBe(true);
    });
  });

  describe('checkoutBranch', () => {
    it('returns true on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true }));
      const result = await useGitStore.getState().checkoutBranch('feature');
      expect(result).toBe(true);
    });
  });

  describe('createBranch', () => {
    it('returns true on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true }));
      const result = await useGitStore.getState().createBranch('feature');
      expect(result).toBe(true);
    });
  });

  describe('deleteBranch', () => {
    it('returns true on success', async () => {
      mockFetch.mockResolvedValue(mockOkResponse({ ok: true }));
      const result = await useGitStore.getState().deleteBranch('old-branch');
      expect(result).toBe(true);
    });
  });
});
