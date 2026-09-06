/**
 * File Store (Zustand)
 * =====================
 * Manages file tree data, loading state, expanded/collapsed paths, workspace path.
 */

import { create } from 'zustand';
import {
  createProjectIdentityHeaders,
  withProjectIdentityPayload,
  withProjectIdentitySearchParams,
} from '../api/projectIdentity';

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

interface FileApiPayload {
  ok?: boolean;
  detail?: string;
  items?: FileTreeItem[];
  workspace?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isFileTreeItem(value: unknown): value is FileTreeItem {
  return isRecord(value)
    && typeof value.name === 'string'
    && typeof value.path === 'string'
    && typeof value.is_dir === 'boolean';
}

async function parseFileResponse(response: Response): Promise<FileApiPayload> {
  if (!response.ok) {
    let errorPayload: unknown;
    try {
      errorPayload = await response.json();
    } catch {
      errorPayload = null;
    }
    const detail = isRecord(errorPayload) && typeof errorPayload.detail === 'string'
      ? errorPayload.detail
      : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }
  const payload: unknown = await response.json();
  if (!isRecord(payload)) {
    throw new Error('Invalid file API response');
  }
  return {
    ok: typeof payload.ok === 'boolean' ? payload.ok : undefined,
    detail: typeof payload.detail === 'string' ? payload.detail : undefined,
    items: Array.isArray(payload.items) ? payload.items.filter(isFileTreeItem) : undefined,
    workspace: typeof payload.workspace === 'string' ? payload.workspace : undefined,
  };
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
      const res = await fetch(withProjectIdentitySearchParams(`/api/fs/list?dir=${encodeURIComponent(dir)}`), {
        headers: createProjectIdentityHeaders(),
      });
      const data = await parseFileResponse(res);
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
        headers: createProjectIdentityHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(withProjectIdentityPayload({ path: folderPath })),
      });
      const data = await parseFileResponse(res);
      return data.ok === true;
    } catch {
      return false;
    }
  },

  renamePath: async (itemPath: string, newName: string) => {
    try {
      const res = await fetch('/api/fs/rename', {
        method: 'POST',
        headers: createProjectIdentityHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(withProjectIdentityPayload({ path: itemPath, new_name: newName })),
      });
      const data = await parseFileResponse(res);
      return { ok: data.ok === true, detail: data.detail };
    } catch {
      return { ok: false, detail: 'Network error' };
    }
  },

  createFile: async (filePath: string, content = '') => {
    try {
      const res = await fetch('/api/fs/write', {
        method: 'POST',
        headers: createProjectIdentityHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(withProjectIdentityPayload({ path: filePath, content })),
      });
      const data = await parseFileResponse(res);
      return data.ok === true;
    } catch {
      return false;
    }
  },

  deletePath: async (itemPath: string) => {
    try {
      const res = await fetch('/api/fs/delete', {
        method: 'DELETE',
        headers: createProjectIdentityHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(withProjectIdentityPayload({ path: itemPath })),
      });
      const data = await parseFileResponse(res);
      return data.ok === true;
    } catch {
      return false;
    }
  },

  getWorkspace: async () => {
    try {
      const res = await fetch(withProjectIdentitySearchParams('/api/fs/workspace'), { headers: createProjectIdentityHeaders() });
      const data = await parseFileResponse(res);
      const wp = data.workspace ?? '/';
      set({ workspacePath: wp });
      return wp;
    } catch {
      return '/';
    }
  },
}));
