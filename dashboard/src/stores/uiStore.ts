/**
 * UI Store (Zustand)
 * ===================
 * Manages global UI state: sidebar, execution mode, modals, system status, toasts.
 */

import { create } from 'zustand';

export type ExecutionMode = 'interactive' | 'plan' | 'build';

/**
 * 운영 지표의 연결 상태 (CR-10).
 * - `unknown`      : 아직 관측 전(첫 응답 대기 중)
 * - `live`         : 최근 관측 성공
 * - `stale`        : 마지막 관측이 오래됨(폴링이 조용히 실패하고 있을 수 있음)
 * - `disconnected` : 요청이 명시적으로 실패
 */
export type SystemConnectionState = 'unknown' | 'live' | 'stale' | 'disconnected';

/**
 * SystemStatus (CR-10)
 * ====================
 * 값이 없는 것(UNKNOWN)과 유효한 0을 구분하기 위해 관측 대상은 `null`을 허용한다.
 * 기본값을 `0`/`true`로 뭉개면 화면이 없는 정보를 있는 것처럼 표시하게 된다.
 */
export interface SystemStatus {
  /** null = 미관측/요청 실패. false로 뭉개지 않는다. */
  healthy: boolean | null;
  backends: Record<string, unknown> | unknown[];
  /** null = 미관측. 0은 실제로 색인된 파일이 없다는 유효값이다. */
  ragFiles: number | null;
  covActive: boolean;
  /** null = 미관측. 0.0%는 유효한 측정값이다. */
  cpuPercent: number | null;
  /** `/api/system/status`의 memory_percent(%). 키 이름이 MB가 아님에 주의. */
  memoryPercent: number | null;
  totalTokens: number | null;
  /** API가 보고한 서버 버전. */
  version: string | null;
  /** API 빌드 식별자(git SHA 등). 미기록이면 null. */
  buildId: string | null;
  /** API 프로세스 가동 시간(초). 화면은 이 값 + 관측 시각으로 보간한다. */
  uptimeSeconds: number | null;
  /** API 프로세스 시작 시각(ISO 8601). */
  startedAt: string | null;
  /** 응답한 API 프로세스 ID — 다중 worker 식별. */
  processId: number | null;
  /** 마지막 **성공** 관측 시각(ms epoch). null = 관측 전. */
  observedAt: number | null;
  /** 연결 상태. */
  state: SystemConnectionState;
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

  pinModalVisible: true,
  commandPaletteVisible: false,
  folderBrowserVisible: false,
  chatHistoryVisible: false,

  systemStatus: {
    healthy: null,
    backends: {},
    ragFiles: null,
    covActive: false,
    cpuPercent: null,
    memoryPercent: null,
    totalTokens: null,
    version: null,
    buildId: null,
    uptimeSeconds: null,
    startedAt: null,
    processId: null,
    observedAt: null,
    state: 'unknown',
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
