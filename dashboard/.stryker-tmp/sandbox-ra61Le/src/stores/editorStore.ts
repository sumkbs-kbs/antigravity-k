/**
 * Editor Store (Zustand)
 * =======================
 * Manages editor tabs, active file, file contents, preview state.
 */
// @ts-nocheck


import { create } from 'zustand';
import { firePluginHook } from '../plugin/pluginRegistry';

export interface OpenFile {
  path: string;
  name: string;
  content: string;
  language: string;
  isDirty: boolean;
}

export interface EditorState {
  // Tabs / Open files
  openFiles: OpenFile[];
  activeFilePath: string | null;

  // Monaco editor instance (for overlay widgets, etc.)
  monacoEditor: any | null;

  // Preview
  previewVisible: boolean;
  previewPath: string | null;
  previewTitle: string;
  previewContent: string;

  // Actions
  openFile: (path: string, name: string, content: string, language?: string) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string) => void;
  setMonacoEditor: (editor: any | null) => void;
  updateFileContent: (path: string, content: string) => void;
  markFileSaved: (path: string) => void;

  // Actions (continued)
  saveFile: (path: string) => Promise<boolean>;

  // Preview
  showPreview: (path: string, title: string, content: string) => void;
  hidePreview: () => void;
}

const EXT_TO_LANG: Record<string, string> = {
  js: 'javascript', ts: 'typescript', tsx: 'typescript', jsx: 'javascript',
  py: 'python', rs: 'rust', go: 'go', java: 'java', kt: 'kotlin',
  swift: 'swift', c: 'c', cpp: 'cpp', h: 'c', hpp: 'cpp',
  css: 'css', scss: 'scss', less: 'less', html: 'html', htm: 'html',
  xml: 'xml', json: 'json', yaml: 'yaml', yml: 'yaml', md: 'markdown',
  sql: 'sql', sh: 'shell', bash: 'shell', zsh: 'shell',
  toml: 'ini', cfg: 'ini', conf: 'ini', ini: 'ini',
  txt: 'plaintext', log: 'plaintext', csv: 'plaintext',
  svg: 'xml', graphql: 'graphql', gql: 'graphql',
  dart: 'dart', lua: 'lua', r: 'r', ruby: 'ruby', rb: 'ruby',
  php: 'php', pl: 'perl', pm: 'perl',
  dockerfile: 'dockerfile', makefile: 'plaintext',
};

export function getLanguageFromExt(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return EXT_TO_LANG[ext] || 'plaintext';
}

export const useEditorStore = create<EditorState>((set, get) => ({
  openFiles: [],
  activeFilePath: null,
  monacoEditor: null,
  previewVisible: false,
  previewPath: null,
  previewTitle: '',
  previewContent: '',

  openFile: (path, name, content, language) => {
    const { openFiles } = get();
    // Check if already open
    const existing = openFiles.find(f => f.path === path);
    if (existing) {
      set({ activeFilePath: path });
      return;
    }

    const lang = language || getLanguageFromExt(name);
    const newFile: OpenFile = {
      path, name, content, language: lang, isDirty: false,
    };

    set({
      openFiles: [...openFiles, newFile],
      activeFilePath: path,
    });
    firePluginHook('file:open', { filePath: path, fileName: name, language: lang });
  },

  closeFile: (path) => {
    const { openFiles, activeFilePath } = get();
    const filtered = openFiles.filter(f => f.path !== path);
    let newActive = activeFilePath;

    if (activeFilePath === path) {
      if (filtered.length > 0) {
        newActive = filtered[filtered.length - 1].path;
      } else {
        newActive = null;
      }
    }

    set({ openFiles: filtered, activeFilePath: newActive });
  },

  setActiveFile: (path) => set({ activeFilePath: path }),

  setMonacoEditor: (editor) => set({ monacoEditor: editor }),

  updateFileContent: (path, content) => {
    set(state => ({
      openFiles: state.openFiles.map(f =>
        f.path === path ? { ...f, content, isDirty: true } : f
      ),
    }));
    setTimeout(() => firePluginHook('file:change', { filePath: path, content }), 0);
  },

  markFileSaved: (path) => {
    set(state => ({
      openFiles: state.openFiles.map(f =>
        f.path === path ? { ...f, isDirty: false } : f
      ),
    }));
  },

  saveFile: async (path) => {
    const state = get();
    const file = state.openFiles.find(f => f.path === path);
    if (!file || !file.isDirty) return true;

    try {
      const res = await fetch('/api/fs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: file.path, content: file.content }),
      });
      const data = await res.json();
      if (data.ok) {
        get().markFileSaved(path);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  showPreview: (path, title, content) => {
    set({
      previewVisible: true,
      previewPath: path,
      previewTitle: title,
      previewContent: content,
    });
  },

  hidePreview: () => {
    set({
      previewVisible: false,
      previewPath: null,
      previewTitle: '',
      previewContent: '',
    });
  },
}));
