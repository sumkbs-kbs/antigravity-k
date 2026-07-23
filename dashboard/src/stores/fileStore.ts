/**
 * File Store (Zustand)
 * =====================
 * Manages file tree data, loading state, expanded/collapsed paths, workspace path.
 */

import { create } from 'zustand';

export interface FileTreeItem {
  name: string;
  path: string;
  is_dir: boolean;
}

export interface FileTreeState {
  treeData: FileTreeItem[];
  isLoading: boolean;
  workspacePath: string;
  expandedPaths: Set<string>;

  // Actions
  setTreeData: (items: FileTreeItem[]) => void;
  setLoading: (val: boolean) => void;
  setWorkspacePath: (path: string) => void;
  toggleExpanded: (path: string) => void;
  isExpanded: (path: string) => boolean;
  refreshTree: () => Promise<void>;
  loadDirectory: (dir?: string) => Promise<FileTreeItem[]>;
  createFolder: (path: string) => Promise<boolean>;
  deletePath: (path: string) => Promise<boolean>;
  renamePath: (path: string, newName: string) => Promise<{ ok: boolean; detail?: string }>;
  createFile: (path: string, content?: string) => Promise<boolean>;
  getWorkspace: () => Promise<string>;
}

export const useFileStore = create<FileTreeState>((set, get) => ({
  treeData: [],
  isLoading: false,
  workspacePath: '/',
  expandedPaths: new Set<string>(),

  setTreeData: (items) => set({ treeData: items }),
  setLoading: (val) => set({ isLoading: val }),
  setWorkspacePath: (path) => set({ workspacePath: path }),

  toggleExpanded: (path) => {
    const { expandedPaths } = get();
    const newSet = new Set(expandedPaths);
    if (newSet.has(path)) {
      newSet.delete(path);
    } else {
      newSet.add(path);
    }
    set({ expandedPaths: newSet });
  },

  isExpanded: (path) => {
    return get().expandedPaths.has(path);
  },

  refreshTree: async () => {
    const { loadDirectory, workspacePath } = get();
    set({ isLoading: true });
    try {
      const items = await loadDirectory('.');
      set({ treeData: items, workspacePath, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  loadDirectory: async (dir = '.') => {
    try {
      const res = await fetch(`/api/fs/list?dir=${encodeURIComponent(dir)}`);
      const data = await res.json();
      return data.items || [];
    } catch (e) {
      console.error('[FileStore] loadDirectory error:', e);
      return [];
    }
  },

  createFolder: async (folderPath: string) => {
    try {
      const res = await fetch('/api/fs/mkdir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: folderPath }),
      });
      const data = await res.json();
      return data.ok === true;
    } catch {
      return false;
    }
  },

  renamePath: async (itemPath: string, newName: string) => {
    try {
      const res = await fetch('/api/fs/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: itemPath, new_name: newName }),
      });
      const data = await res.json();
      return { ok: data.ok === true, detail: data.detail };
    } catch {
      return { ok: false, detail: 'Network error' };
    }
  },

  createFile: async (filePath: string, content = '') => {
    try {
      const res = await fetch('/api/fs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath, content }),
      });
      const data = await res.json();
      return data.ok === true;
    } catch {
      return false;
    }
  },

  deletePath: async (itemPath: string) => {
    try {
      const res = await fetch('/api/fs/delete', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: itemPath }),
      });
      const data = await res.json();
      return data.ok === true;
    } catch {
      return false;
    }
  },

  getWorkspace: async () => {
    try {
      const res = await fetch('/api/fs/workspace');
      const data = await res.json();
      const wp = data.workspace || '/';
      set({ workspacePath: wp });
      return wp;
    } catch {
      return '/';
    }
  },
}));
