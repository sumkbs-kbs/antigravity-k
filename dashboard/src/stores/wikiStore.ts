/**
 * Wiki Store (Zustand)
 * =====================
 * Manages wiki/vault state: tree, current document, vault path, search.
 */

import { create } from 'zustand';

export interface WikiTreeItem {
  name: string;
  path: string;
  type: 'file' | 'folder';
  children?: WikiTreeItem[];
}

export interface WikiDocument {
  path: string;
  content: string;
  metadata: Record<string, any>;
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
  saveDocument: (path: string, content: string, metadata?: Record<string, any>) => Promise<boolean>;
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
        await fetch('/api/vault/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ vault_path: savedPath }),
        });
      } catch { /* ignore */ }
    }
    try {
      const resp = await fetch('/api/vault/config');
      const data = await resp.json();
      if (data.ok) {
        set({ vaultPath: data.vault_path });
        localStorage.setItem(VAULT_PATH_KEY, data.vault_path);
      }
    } catch { /* ignore */ }
    await get().loadTree();
  },

  loadTree: async () => {
    try {
      const resp = await fetch('/api/vault/tree');
      const data = await resp.json();
      if (data.vault_path) {
        set({ vaultPath: data.vault_path });
        localStorage.setItem(VAULT_PATH_KEY, data.vault_path);
      }
      set({ treeData: data.tree || [] });
    } catch { /* ignore */ }
  },

  loadDocument: async (path) => {
    try {
      const resp = await fetch(`/api/vault/read?path=${encodeURIComponent(path)}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      set({
        currentDoc: { path, content: data.content || '', metadata: data.metadata || {} },
        isEditing: false,
        editContent: data.content || '',
      });
    } catch (err: any) {
      console.error('Wiki load error:', err);
    }
  },

  saveDocument: async (path, content, metadata) => {
    try {
      const resp = await fetch('/api/vault/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content, metadata: metadata || get().currentDoc?.metadata || {} }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content, metadata }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
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
      const resp = await fetch(`/v1/notes/search?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      const results = [
        ...(data.keyword_results || []),
        ...(data.semantic_results || []).map((r: any) => r.metadata?.source || r.id),
      ];
      set({ searchResults: [...new Set(results)] });
    } catch {
      set({ searchResults: [] });
    }
  },

  updateVaultConfig: async (path) => {
    try {
      const resp = await fetch('/api/vault/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vault_path: path }),
      });
      const data = await resp.json();
      if (data.ok) {
        set({ vaultPath: data.vault_path });
        localStorage.setItem(VAULT_PATH_KEY, data.vault_path);
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
