/**
 * File Store (Zustand)
 * =====================
 * Manages file tree data, loading state, expanded/collapsed paths, workspace path.
 * WS-04: switchEpoch gate + AbortController so stale B→C list responses never merge.
 */

import { create } from 'zustand';
import {
  createProjectIdentityHeaders,
  isIdentityCurrent,
  withProjectIdentityPayload,
  withProjectIdentitySearchParams,
} from '../api/projectIdentity';
import { useProjectStore } from './projectStore';

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
  clearForProjectSwitch: () => void;
  refreshTree: () => Promise<void>;
  loadDirectory: (dir?: string, options?: { signal?: AbortSignal }) => Promise<FileTreeItem[]>;
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

/** In-flight list/workspace fetches — aborted on project switch. */
let inflightController: AbortController | null = null;

function abortInflightFetches(): void {
  if (inflightController) {
    inflightController.abort();
    inflightController = null;
  }
}

function beginInflightFetch(_epoch: number): AbortController {
  abortInflightFetches();
  const controller = new AbortController();
  inflightController = controller;
  return controller;
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

  clearForProjectSwitch: () => {
    abortInflightFetches();
    set({
      treeData: [],
      expandedPaths: new Set<string>(),
      isLoading: false,
    });
  },

  refreshTree: async () => {
    const capturedEpoch = useProjectStore.getState().switchEpoch;
    const controller = beginInflightFetch(capturedEpoch);
    const { loadDirectory, workspacePath } = get();
    set({ isLoading: true });
    try {
      const items = await loadDirectory('.', { signal: controller.signal });
      if (!isIdentityCurrent(capturedEpoch) || controller.signal.aborted) {
        return;
      }
      set({ treeData: items, workspacePath, isLoading: false });
    } catch (e) {
      if (controller.signal.aborted || !isIdentityCurrent(capturedEpoch)) {
        return;
      }
      console.error('[FileStore] refreshTree error:', e);
      set({ isLoading: false });
    } finally {
      if (inflightController === controller) {
        inflightController = null;
          }
    }
  },

  loadDirectory: async (dir = '.', options) => {
    try {
      const res = await fetch(withProjectIdentitySearchParams(`/api/fs/list?dir=${encodeURIComponent(dir)}`), {
        headers: createProjectIdentityHeaders(),
        signal: options?.signal,
      });
      const data = await parseFileResponse(res);
      return data.items || [];
    } catch (e) {
      if (options?.signal?.aborted || (e instanceof DOMException && e.name === 'AbortError')) {
        return [];
      }
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
    const capturedEpoch = useProjectStore.getState().switchEpoch;
    const controller = beginInflightFetch(capturedEpoch);
    try {
      const res = await fetch(withProjectIdentitySearchParams('/api/fs/workspace'), {
        headers: createProjectIdentityHeaders(),
        signal: controller.signal,
      });
      const data = await parseFileResponse(res);
      const wp = data.workspace ?? '/';
      if (!isIdentityCurrent(capturedEpoch) || controller.signal.aborted) {
        return wp;
      }
      set({ workspacePath: wp });
      return wp;
    } catch (e) {
      if (controller.signal.aborted || (e instanceof DOMException && e.name === 'AbortError')) {
        return '/';
      }
      return '/';
    } finally {
      if (inflightController === controller) {
        inflightController = null;
          }
    }
  },
}));

/** Abort + clear tree as soon as project identity switches (before Sidebar refresh). */
if (typeof window !== 'undefined') {
  window.addEventListener('agk:project-switched', () => {
    abortInflightFetches();
    useFileStore.setState({
      treeData: [],
      expandedPaths: new Set<string>(),
      isLoading: false,
    });
  });
}
