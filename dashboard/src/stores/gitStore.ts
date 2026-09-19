/**
 * Git Store (Zustand)
 * =====================
 * Manages Git state: status, log, branches, staging, diff.
 */

import { create } from 'zustand';
import { firePluginHook } from '../plugin/pluginRegistry';
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
} from './gitApi';
import type { GitState } from './gitStoreTypes';

export type { GitBranch, GitCommit, GitFile, GitGraphNode, GitStash } from './gitSchema';
export type { GitState } from './gitStoreTypes';

function gitErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown Git error';
}

export const useGitStore = create<GitState>((set, get) => ({
  status: {
    loading: false,
    branch: '',
    upstream: null,
    ahead: 0,
    behind: 0,
    files: [],
    counts: { staged: 0, unstaged: 0, untracked: 0, total: 0 },
    error: null,
  },

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

  fetchStatus: async (path = '.') => {
    set(s => ({ status: { ...s.status, loading: true, error: null } }));
    try {
      const data = await fetchGitStatus(path);
      if (data.ok) {
        set({
          status: {
            loading: false,
            branch: data.branch,
            upstream: data.upstream,
            ahead: data.ahead,
            behind: data.behind,
            files: data.files,
            counts: data.counts,
            error: null,
          },
        });
      } else {
        set(s => ({ status: { ...s.status, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (error: unknown) {
      set(s => ({ status: { ...s.status, loading: false, error: gitErrorMessage(error) } }));
    }
  },

  fetchLog: async (path = '.', count = 20, branch = '') => {
    set(s => ({ log: { ...s.log, loading: true, error: null } }));
    try {
      const data = await fetchGitLog(path, count, branch);
      if (data.ok) {
        set({ log: { loading: false, commits: data.commits, error: null } });
      } else {
        set(s => ({ log: { ...s.log, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (error: unknown) {
      set(s => ({ log: { ...s.log, loading: false, error: gitErrorMessage(error) } }));
    }
  },

  fetchBranches: async (path = '.') => {
    set(s => ({ branches: { ...s.branches, loading: true, error: null } }));
    try {
      const data = await fetchGitBranches(path);
      if (data.ok) {
        set({
          branches: {
            loading: false,
            list: data.branches,
            current: data.current,
            error: null,
          },
        });
      } else {
        set(s => ({ branches: { ...s.branches, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (error: unknown) {
      set(s => ({ branches: { ...s.branches, loading: false, error: gitErrorMessage(error) } }));
    }
  },

  fetchDiff: async (file = '', staged = false, path = '.') => {
    set(s => ({ diff: { ...s.diff, loading: true, error: null } }));
    try {
      const data = await fetchGitDiff(file, staged, path);
      if (data.ok) {
        set({ diff: { loading: false, content: data.diff, stat: data.stat, error: null } });
      } else {
        set(s => ({ diff: { ...s.diff, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (error: unknown) {
      set(s => ({ diff: { ...s.diff, loading: false, error: gitErrorMessage(error) } }));
    }
  },

  fetchGraph: async (path = '.', count = 30) => {
    set(s => ({ graph: { ...s.graph, loading: true, error: null } }));
    try {
      const data = await fetchGitGraph(path, count);
      if (data.ok) {
        set({ graph: { loading: false, nodes: data.nodes, error: null } });
      } else {
        set(s => ({ graph: { ...s.graph, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (error: unknown) {
      set(s => ({ graph: { ...s.graph, loading: false, error: gitErrorMessage(error) } }));
    }
  },

  stageFiles: async (files, path = '.') => {
    try {
      const data = await stageGitFiles(files, path);
      if (data.ok) {
        await get().fetchStatus(path);
        return true;
      }
      return false;
    } catch { return false; }
  },

  unstageFiles: async (files, path = '.') => {
    try {
      const data = await unstageGitFiles(files, path);
      if (data.ok) {
        await get().fetchStatus(path);
        return true;
      }
      return false;
    } catch { return false; }
  },

  commit: async (message, stageAll = true, path = '.') => {
    try {
      const data = await commitGit(message, stageAll, path);
      if (data.ok) {
        await get().fetchStatus(path);
        await get().fetchLog(path);
        await get().fetchGraph(path);
        firePluginHook('git:commit', { message, path });
        return true;
      }
      return false;
    } catch { return false; }
  },

  checkoutBranch: async (name, path = '.') => {
    try {
      const data = await checkoutGitBranch(name, path);
      if (data.ok) {
        await Promise.all([
          get().fetchStatus(path),
          get().fetchBranches(path),
          get().fetchLog(path),
        ]);
        return true;
      }
      return false;
    } catch { return false; }
  },

  createBranch: async (name, from = '', path = '.') => {
    try {
      const data = await createGitBranch(name, from, path);
      if (data.ok) {
        await Promise.all([
          get().fetchBranches(path),
          get().fetchStatus(path),
        ]);
        return true;
      }
      return false;
    } catch { return false; }
  },

  deleteBranch: async (name, force = false, path = '.') => {
    try {
      const data = await deleteGitBranch(name, force, path);
      if (data.ok) {
        await get().fetchBranches(path);
        return true;
      }
      return false;
    } catch { return false; }
  },

  setCommitDialogOpen: (open) => set({ commitDialogOpen: open, commitMessage: '' }),
  setCommitMessage: (msg) => set({ commitMessage: msg }),
  setCommitStageAll: (val) => set({ commitStageAll: val }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setSelectedLogCommit: (commit) => set({ selectedLogCommit: commit }),
  setShowStagedDiff: (show) => set({ showStagedDiff: show }),
}));
