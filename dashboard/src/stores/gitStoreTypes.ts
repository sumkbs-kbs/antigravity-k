import type { GitBranch, GitCommit, GitFile, GitGraphNode } from './gitSchema';

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
