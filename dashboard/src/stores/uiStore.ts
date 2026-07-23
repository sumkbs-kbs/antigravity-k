/**
 * UI Store (Zustand)
 * ===================
 * Manages global UI state: sidebar, execution mode, modals, system status, toasts.
 */

import { create } from 'zustand';

export type ExecutionMode = 'interactive' | 'plan' | 'build';

export interface SystemStatus {
  healthy: boolean;
  backends: Record<string, any>;
  ragFiles: number;
  covActive: boolean;
  cpuPercent: number;
  memoryMb: number;
  totalTokens: number;
}

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

export interface UiState {
  // Sidebar
  sidebarVisible: boolean;
  sidebarWidth: number;

  // Execution mode
  mode: ExecutionMode;

  // Modals
  pinModalVisible: boolean;
  commandPaletteVisible: boolean;
  folderBrowserVisible: boolean;
  chatHistoryVisible: boolean;

  // System
  systemStatus: SystemStatus;
  providerBadges: Array<{ name: string; key: string; icon: string; active: boolean }>;

  // Toasts
  toasts: Toast[];

  // Workspace
  workspacePath: string;

  // Actions
  toggleSidebar: () => void;
  setSidebarVisible: (val: boolean) => void;
  setMode: (mode: ExecutionMode) => void;
  setPinModalVisible: (val: boolean) => void;
  setCommandPaletteVisible: (val: boolean) => void;
  setFolderBrowserVisible: (val: boolean) => void;
  setChatHistoryVisible: (val: boolean) => void;
  setSystemStatus: (status: Partial<SystemStatus>) => void;
  addToast: (message: string, type?: 'success' | 'error' | 'info') => void;
  removeToast: (id: string) => void;
  setWorkspacePath: (path: string) => void;
}

export const useUiStore = create<UiState>((set, get) => ({
  sidebarVisible: true,
  sidebarWidth: 220,

  mode: 'interactive',

  pinModalVisible: false,
  commandPaletteVisible: false,
  folderBrowserVisible: false,
  chatHistoryVisible: false,

  systemStatus: {
    healthy: false,
    backends: {},
    ragFiles: 0,
    covActive: false,
    cpuPercent: 0,
    memoryMb: 0,
    totalTokens: 0,
  },

  providerBadges: [],

  toasts: [],

  workspacePath: '/',

  toggleSidebar: () => set(state => ({ sidebarVisible: !state.sidebarVisible })),
  setSidebarVisible: (val) => set({ sidebarVisible: val }),
  setMode: (mode) => set({ mode }),

  setPinModalVisible: (val) => set({ pinModalVisible: val }),
  setCommandPaletteVisible: (val) => set({ commandPaletteVisible: val }),
  setFolderBrowserVisible: (val) => set({ folderBrowserVisible: val }),
  setChatHistoryVisible: (val) => set({ chatHistoryVisible: val }),

  setSystemStatus: (status) =>
    set(state => ({
      systemStatus: { ...state.systemStatus, ...status },
    })),

  addToast: (message, type = 'info') => {
    const id = Math.random().toString(36).substr(2, 6);
    set(state => ({
      toasts: [...state.toasts, { id, message, type }],
    }));
    setTimeout(() => {
      get().removeToast(id);
    }, 3000);
  },

  removeToast: (id) =>
    set(state => ({
      toasts: state.toasts.filter(t => t.id !== id),
    })),

  setWorkspacePath: (path) => set({ workspacePath: path }),
}));
