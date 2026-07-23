/**
 * Git Store (Zustand)
 * =====================
 * Manages Git state: status, log, branches, staging, diff.
 */

import { create } from 'zustand';
import { firePluginHook } from '../plugin/pluginRegistry';

export interface GitFile {
  x: string;
  y: string;
  staged_status: string;
  unstaged_status: string;
  file_path: string;
  old_path?: string | null;
  is_renamed?: boolean;
}

export interface GitCommit {
  hash: string;
  short_hash: string;
  author_name: string;
  author_email: string;
  date: string;
  message: string;
  refs?: string;
}

export interface GitBranch {
  name: string;
  is_current: boolean;
  is_remote: boolean;
  upstream?: string | null;
}

export interface GitStash {
  short_hash: string;
  date: string;
  message: string;
}

export interface GitGraphNode {
  graph: string;
  hash: string;
  short_hash: string;
  author: string;
  message: string;
  date: string;
  refs: string;
}

export interface GitState {
  status: {
    loading: boolean;
    branch: string;
    upstream: string | null;
    ahead: number;
    behind: number;
    files: GitFile[];
    counts: { staged: number; unstaged: number; untracked: number; total: number };
    error: string | null;
  };

  log: {
    loading: boolean;
    commits: GitCommit[];
    error: string | null;
  };

  branches: {
    loading: boolean;
    list: GitBranch[];
    current: string;
    error: string | null;
  };

  diff: {
    loading: boolean;
    content: string;
    stat: string;
    error: string | null;
  };

  graph: {
    loading: boolean;
    nodes: GitGraphNode[];
    error: string | null;
  };

  commitDialogOpen: boolean;
  commitMessage: string;
  commitStageAll: boolean;

  activeTab: 'status' | 'log' | 'branches' | 'graph';
  selectedLogCommit: GitCommit | null;
  showStagedDiff: boolean;

  // Actions
  fetchStatus: (path?: string) => Promise<void>;
  fetchLog: (path?: string, count?: number, branch?: string) => Promise<void>;
  fetchBranches: (path?: string) => Promise<void>;
  fetchDiff: (file?: string, staged?: boolean, path?: string) => Promise<void>;
  fetchGraph: (path?: string, count?: number) => Promise<void>;
  stageFiles: (files: string[], path?: string) => Promise<boolean>;
  unstageFiles: (files: string[], path?: string) => Promise<boolean>;
  commit: (message: string, stageAll?: boolean, path?: string) => Promise<boolean>;
  checkoutBranch: (name: string, path?: string) => Promise<boolean>;
  createBranch: (name: string, from?: string, path?: string) => Promise<boolean>;
  deleteBranch: (name: string, force?: boolean, path?: string) => Promise<boolean>;

  setCommitDialogOpen: (open: boolean) => void;
  setCommitMessage: (msg: string) => void;
  setCommitStageAll: (val: boolean) => void;
  setActiveTab: (tab: 'status' | 'log' | 'branches' | 'graph') => void;
  setSelectedLogCommit: (commit: GitCommit | null) => void;
  setShowStagedDiff: (show: boolean) => void;
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
      const res = await fetch(`/api/git/status?path=${encodeURIComponent(path)}`);
      const data = await res.json();
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
    } catch (err: any) {
      set(s => ({ status: { ...s.status, loading: false, error: err.message } }));
    }
  },

  fetchLog: async (path = '.', count = 20, branch = '') => {
    set(s => ({ log: { ...s.log, loading: true, error: null } }));
    try {
      const res = await fetch('/api/git/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, count, branch }),
      });
      const data = await res.json();
      if (data.ok) {
        set({ log: { loading: false, commits: data.commits, error: null } });
      } else {
        set(s => ({ log: { ...s.log, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (err: any) {
      set(s => ({ log: { ...s.log, loading: false, error: err.message } }));
    }
  },

  fetchBranches: async (path = '.') => {
    set(s => ({ branches: { ...s.branches, loading: true, error: null } }));
    try {
      const res = await fetch(`/api/git/branches?path=${encodeURIComponent(path)}`);
      const data = await res.json();
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
    } catch (err: any) {
      set(s => ({ branches: { ...s.branches, loading: false, error: err.message } }));
    }
  },

  fetchDiff: async (file = '', staged = false, path = '.') => {
    set(s => ({ diff: { ...s.diff, loading: true, error: null } }));
    try {
      const res = await fetch('/api/git/diff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, file, staged }),
      });
      const data = await res.json();
      if (data.ok) {
        set({ diff: { loading: false, content: data.diff, stat: data.stat, error: null } });
      } else {
        set(s => ({ diff: { ...s.diff, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (err: any) {
      set(s => ({ diff: { ...s.diff, loading: false, error: err.message } }));
    }
  },

  fetchGraph: async (path = '.', count = 30) => {
    set(s => ({ graph: { ...s.graph, loading: true, error: null } }));
    try {
      const res = await fetch(`/api/git/graph?path=${encodeURIComponent(path)}&count=${count}`);
      const data = await res.json();
      if (data.ok) {
        set({ graph: { loading: false, nodes: data.nodes, error: null } });
      } else {
        set(s => ({ graph: { ...s.graph, loading: false, error: data.error || 'Failed' } }));
      }
    } catch (err: any) {
      set(s => ({ graph: { ...s.graph, loading: false, error: err.message } }));
    }
  },

  stageFiles: async (files, path = '.') => {
    try {
      const res = await fetch('/api/git/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, files, all: files.length === 0 }),
      });
      const data = await res.json();
      if (data.ok) {
        await get().fetchStatus(path);
        return true;
      }
      return false;
    } catch { return false; }
  },

  unstageFiles: async (files, path = '.') => {
    try {
      const res = await fetch('/api/git/unstage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, files }),
      });
      const data = await res.json();
      if (data.ok) {
        await get().fetchStatus(path);
        return true;
      }
      return false;
    } catch { return false; }
  },

  commit: async (message, stageAll = true, path = '.') => {
    try {
      const res = await fetch('/api/git/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, message, stage_all: stageAll }),
      });
      const data = await res.json();
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
      const res = await fetch('/api/git/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, name }),
      });
      const data = await res.json();
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
      const res = await fetch('/api/git/branch/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, name, from }),
      });
      const data = await res.json();
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
      const res = await fetch('/api/git/branch/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, name, force }),
      });
      const data = await res.json();
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
