/**
 * Wiki Store (Zustand)
 * =====================
 * Manages wiki/vault state: tree, current document, vault path, search.
 */

import { create } from 'zustand';
import { createAccessPinHeaders } from '../utils/accessPinCredential';

export interface WikiTreeItem {
  name: string;
  path: string;
  type: 'file' | 'folder';
  children?: WikiTreeItem[];
}

export interface WikiDocument {
  path: string;
  content: string;
  metadata: Record<string, unknown>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isWikiTreeItem(value: unknown): value is WikiTreeItem {
  if (!isRecord(value) || typeof value.name !== 'string' || typeof value.path !== 'string') return false;
  if (value.type !== 'file' && value.type !== 'folder') return false;
  return value.children === undefined
    || (Array.isArray(value.children) && value.children.every(isWikiTreeItem));
}

export interface WikiState {
  vaultPath: string;
  treeData: WikiTreeItem[];
  currentDoc: WikiDocument | null;
  isEditing: boolean;
  editContent: string;
  searchQuery: string;
  searchResults: string[];
  isLoading: boolean;

  // Actions
  setVaultPath: (path: string) => void;
  setTreeData: (items: WikiTreeItem[]) => void;
  setCurrentDoc: (doc: WikiDocument | null) => void;
  setIsEditing: (val: boolean) => void;
  setEditContent: (content: string) => void;
  setSearchQuery: (q: string) => void;
  setSearchResults: (results: string[]) => void;
  setLoading: (val: boolean) => void;

  // API
  initVault: () => Promise<void>;
  loadTree: () => Promise<void>;
  loadDocument: (path: string) => Promise<void>;
  saveDocument: (path: string, content: string, metadata?: Record<string, unknown>) => Promise<boolean>;
  createDocument: (path: string, title: string, tags: string[]) => Promise<boolean>;
  searchDocuments: (q: string) => Promise<void>;
  updateVaultConfig: (path: string) => Promise<boolean>;
}

const VAULT_PATH_KEY = 'antigravity_vault_path';

export const useWikiStore = create<WikiState>((set, get) => ({
  vaultPath: '',
  treeData: [],
  currentDoc: null,
  isEditing: false,
  editContent: '',
  searchQuery: '',
  searchResults: [],
  isLoading: false,

  setVaultPath: (path) => set({ vaultPath: path }),
  setTreeData: (items) => set({ treeData: items }),
  setCurrentDoc: (doc) => set({ currentDoc: doc }),
  setIsEditing: (val) => set({ isEditing: val }),
  setEditContent: (content) => set({ editContent: content }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setSearchResults: (results) => set({ searchResults: results }),
  setLoading: (val) => set({ isLoading: val }),

  initVault: async () => {
    const savedPath = localStorage.getItem(VAULT_PATH_KEY);
    if (savedPath) {
      try {
        const resp = await fetch('/api/vault/config', {
          method: 'POST',
          headers: createAccessPinHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ vault_path: savedPath }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      } catch { /* ignore */ }
    }
    try {
      const resp = await fetch('/api/vault/config', { headers: createAccessPinHeaders() });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      if (isRecord(rawData) && rawData.ok === true && typeof rawData.vault_path === 'string') {
        set({ vaultPath: rawData.vault_path });
        localStorage.setItem(VAULT_PATH_KEY, rawData.vault_path);
      }
    } catch { /* ignore */ }
    await get().loadTree();
  },

  loadTree: async () => {
    try {
      const resp = await fetch('/api/vault/tree', { headers: createAccessPinHeaders() });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      if (!isRecord(rawData)) throw new Error('Invalid Vault tree response');
      if (typeof rawData.vault_path === 'string' && rawData.vault_path.length > 0) {
        set({ vaultPath: rawData.vault_path });
        localStorage.setItem(VAULT_PATH_KEY, rawData.vault_path);
      }
      const treeData = Array.isArray(rawData.tree) ? rawData.tree.filter(isWikiTreeItem) : [];
      set({ treeData });
    } catch { /* ignore */ }
  },

  loadDocument: async (path) => {
    try {
      const resp = await fetch(`/api/vault/read?path=${encodeURIComponent(path)}`, {
        headers: createAccessPinHeaders(),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      if (!isRecord(rawData) || typeof rawData.content !== 'string') {
        throw new Error('Invalid Vault document response');
      }
      const metadata = isRecord(rawData.metadata) ? rawData.metadata : {};
      set({
        currentDoc: { path, content: rawData.content, metadata },
        isEditing: false,
        editContent: rawData.content,
      });
    } catch (err) {
      console.error('Wiki load error:', err instanceof Error ? err.message : String(err));
    }
  },

  saveDocument: async (path, content, metadata) => {
    try {
      const resp = await fetch('/api/vault/write', {
        method: 'POST',
        headers: createAccessPinHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ path, content, metadata: metadata || get().currentDoc?.metadata || {} }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      if (!isRecord(rawData) || rawData.ok !== true) return false;
      set({ isEditing: false });
      await get().loadDocument(path);
      return true;
    } catch {
      return false;
    }
  },

  createDocument: async (path, title, tags) => {
    const content = `\n# ${title}\n\n여기에 내용을 작성하세요.\n`;
    const metadata = { title, tags, date: new Date().toISOString().split('T')[0] };
    try {
      const resp = await fetch('/api/vault/write', {
        method: 'POST',
        headers: createAccessPinHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ path, content, metadata }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      if (!isRecord(rawData) || rawData.ok !== true) return false;
      await get().loadTree();
      await get().loadDocument(path);
      return true;
    } catch {
      return false;
    }
  },

  searchDocuments: async (q) => {
    if (!q.trim()) {
      set({ searchResults: [] });
      await get().loadTree();
      return;
    }
    try {
      const resp = await fetch(`/v1/notes/search?q=${encodeURIComponent(q)}`, {
        headers: createAccessPinHeaders(),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      const data = isRecord(rawData) ? rawData : {};
      const keywordResults = Array.isArray(data.keyword_results)
        ? data.keyword_results.filter((item): item is string => typeof item === 'string')
        : [];
      const semanticResults = Array.isArray(data.semantic_results)
        ? data.semantic_results.flatMap((item) => {
            if (!isRecord(item)) return [];
            const metadata = isRecord(item.metadata) ? item.metadata : {};
            const source = typeof metadata.source === 'string' ? metadata.source : undefined;
            const id = typeof item.id === 'string' ? item.id : undefined;
            const result = source ?? id;
            return result ? [result] : [];
          })
        : [];
      const results = [...keywordResults, ...semanticResults];
      set({ searchResults: [...new Set(results)] });
    } catch {
      set({ searchResults: [] });
    }
  },

  updateVaultConfig: async (path) => {
    try {
      const resp = await fetch('/api/vault/config', {
        method: 'POST',
        headers: createAccessPinHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ vault_path: path }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      if (isRecord(rawData) && rawData.ok === true && typeof rawData.vault_path === 'string') {
        set({ vaultPath: rawData.vault_path });
        localStorage.setItem(VAULT_PATH_KEY, rawData.vault_path);
        await get().loadTree();
        set({ currentDoc: null });
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },
}));
