/**
 * Activity Store (Zustand)
 * ========================
 * Accumulates live agent activity rows for the chat feed timeline —
 * the Antigravity-style "파일 수정함 / 명령을 실행함 / 파일을 읽음"
 * collapsible strip. Fed by the /v1/ws/events socket (ToolExecution*,
 * FileOpened/Modified, FailureDetected, PlanningModeStarted).
 *
 * Extended with session-level stats for the Agent Monitoring Panel:
 * - Token usage (prompt / completion / total)
 * - Session timer (started / ended timestamps)
 * - Active tool tracking (currently running tool name + start time)
 * - Error counters
 */

import { create } from 'zustand';

export type ActivityKind = 'tool' | 'file_read' | 'file_edit' | 'error' | 'plan';
export type ActivityStatus = 'running' | 'done' | 'failed';

export interface ActivityItem {
  id: string;
  kind: ActivityKind;
  label: string;
  detail: string;
  status: ActivityStatus;
  at: number;
}

export interface ToolExecutionEventData {
  name?: string;
  tool_name?: string;
  [key: string]: unknown;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface ActiveTool {
  name: string;
  startedAt: number;
}

const MAX_ITEMS = 60;
const DEDUPE_WINDOW_MS = 1_500;

function pickString(data: Record<string, unknown>, keys: readonly string[]): string {
  for (const key of keys) {
    const value = data[key];
    if (typeof value === 'string' && value.trim().length > 0) return value.trim();
  }
  return '';
}

function toolLabel(toolName: string): string {
  const map: Record<string, string> = {
    web_search: '웹 검색',
    run_bash_command: '명령 실행',
    aishell: '명령 실행',
    read_file: '파일 읽음',
    list_directory: '디렉터리 탐색',
    replace_file_content: '파일 수정함',
  };
  return map[toolName] ?? `도구: ${toolName}`;
}

function detailForTool(toolName: string, data: Record<string, unknown>): string {
  const specific = pickString(data, ['command', 'cmd', 'filepath', 'file_path', 'query', 'path', 'url']);
  if (specific) return specific;
  const generic = pickString(data, ['description', 'objective', 'args']);
  return generic || toolName;
}

interface ActivityState {
  items: ActivityItem[];

  /** Token usage for the current session */
  tokenUsage: TokenUsage;

  /** Session timing */
  sessionStartedAt: number | null;
  sessionEndedAt: number | null;

  /** Currently executing tool */
  activeTool: ActiveTool | null;

  /** Cumulative counters */
  errorCount: number;
  toolCallCount: number;
  fileEditCount: number;
  fileReadCount: number;

  recordToolStart: (data: ToolExecutionEventData) => void;
  recordToolEnd: () => void;
  recordFileRead: (path: string) => void;
  recordFileEdit: (path: string) => void;
  recordError: (message: string) => void;
  recordPlan: (goal: string) => void;

  /** New actions for the monitoring panel */
  recordTokenUsage: (prompt: number, completion: number) => void;
  setSessionStarted: () => void;
  setSessionEnded: () => void;

  clear: () => void;
}

let activityCounter = 0;

function nextId(): string {
  activityCounter += 1;
  return `act_${Date.now().toString(36)}_${activityCounter}`;
}

export const useActivityStore = create<ActivityState>((set, get) => {
  /** Same kind+detail within the dedupe window updates the timestamp only. */
  function pushItem(item: Omit<ActivityItem, 'id' | 'at'> & { at?: number }): void {
    const now = item.at ?? Date.now();
    const items = get().items;
    const last = items[items.length - 1];
    if (last && last.kind === item.kind && last.detail === item.detail && now - last.at < DEDUPE_WINDOW_MS) {
      set({ items: [...items.slice(0, -1), { ...last, at: now, status: item.status }] });
      return;
    }
    const next: ActivityItem = { ...item, id: nextId(), at: now };
    set({ items: [...items, next].slice(-MAX_ITEMS) });
  }

  return {
    items: [],
    tokenUsage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
    sessionStartedAt: null,
    sessionEndedAt: null,
    activeTool: null,
    errorCount: 0,
    toolCallCount: 0,
    fileEditCount: 0,
    fileReadCount: 0,

    recordToolStart: (data) => {
      const toolName = (data.tool_name ?? data.name ?? 'tool').toString();
      set((s) => ({
        activeTool: { name: toolName, startedAt: Date.now() },
        toolCallCount: s.toolCallCount + 1,
      }));
      pushItem({
        kind: 'tool',
        label: toolLabel(toolName),
        detail: detailForTool(toolName, data),
        status: 'running',
      });
    },

    recordToolEnd: () => {
      set({ activeTool: null });
      const items = get().items;
      for (let i = items.length - 1; i >= 0; i -= 1) {
        if (items[i].kind === 'tool' && items[i].status === 'running') {
          const updated = [...items];
          updated[i] = { ...updated[i], status: 'done' };
          set({ items: updated });
          return;
        }
      }
    },

    recordFileRead: (path) => {
      if (!path) return;
      set((s) => ({ fileReadCount: s.fileReadCount + 1 }));
      pushItem({ kind: 'file_read', label: '파일 읽음', detail: path, status: 'done' });
    },

    recordFileEdit: (path) => {
      if (!path) return;
      set((s) => ({ fileEditCount: s.fileEditCount + 1 }));
      pushItem({ kind: 'file_edit', label: '파일 수정함', detail: path, status: 'done' });
    },

    recordError: (message) => {
      if (!message) return;
      set((s) => ({ errorCount: s.errorCount + 1 }));
      pushItem({ kind: 'error', label: '오류 감지', detail: message, status: 'failed' });
    },

    recordPlan: (goal) => {
      pushItem({ kind: 'plan', label: '계획 수립', detail: goal || '계획 모드', status: 'running' });
    },

    recordTokenUsage: (prompt, completion) => {
      set((s) => ({
        tokenUsage: {
          promptTokens: s.tokenUsage.promptTokens + prompt,
          completionTokens: s.tokenUsage.completionTokens + completion,
          totalTokens: s.tokenUsage.totalTokens + prompt + completion,
        },
      }));
    },

    setSessionStarted: () => {
      set({ sessionStartedAt: Date.now(), sessionEndedAt: null });
    },

    setSessionEnded: () => {
      set({ sessionEndedAt: Date.now(), activeTool: null });
    },

    clear: () => set({
      items: [],
      tokenUsage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
      sessionStartedAt: null,
      sessionEndedAt: null,
      activeTool: null,
      errorCount: 0,
      toolCallCount: 0,
      fileEditCount: 0,
      fileReadCount: 0,
    }),
  };
});
