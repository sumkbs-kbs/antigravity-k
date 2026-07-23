/**
 * Agent Monitor Store (Zustand)
 * ==============================
 * Manages real-time agent monitoring state: current agent status,
 * live log stream from tool execution, task progress, and execution history.
 */

import { create } from 'zustand';

/* ─── Types ────────────────────────────────────────────────── */

export type AgentStatus = 'idle' | 'running' | 'planning' | 'error' | 'thinking';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug' | 'success';
  source: string;
  message: string;
  /** Optional structured metadata */
  data?: Record<string, any>;
}

export interface ActiveTool {
  name: string;
  startedAt: string;
  /** Duration in seconds (updated live) */
  duration: number;
  status: 'running' | 'completed' | 'failed';
}

export interface TaskProgress {
  id: string;
  title: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0–100
  startedAt?: string;
  completedAt?: string;
  type?: string;
}

export interface ExecutionEvent {
  id: string;
  timestamp: string;
  type: 'tool_start' | 'tool_end' | 'task_start' | 'task_end' | 'error' | 'plan' | 'mode_change';
  label: string;
  detail?: string;
}

export interface AgentMonitorState {
  // Current agent status
  agentStatus: AgentStatus;
  // Active tool being executed
  activeTool: ActiveTool | null;
  // Live log stream (ring buffer)
  logs: LogEntry[];
  // Current task progress
  currentTasks: TaskProgress[];
  // Execution history timeline (recent events)
  timeline: ExecutionEvent[];
  // System metrics (updated live)
  uptime: number;
  memoryMb: number;
  cpuPercent: number;
  totalTokens: number;

  // Actions
  setAgentStatus: (status: AgentStatus) => void;
  setActiveTool: (tool: ActiveTool | null) => void;
  addLog: (entry: Omit<LogEntry, 'id' | 'timestamp'>) => void;
  updateTaskProgress: (taskId: string, updates: Partial<TaskProgress>) => void;
  addTask: (task: TaskProgress) => void;
  removeTask: (taskId: string) => void;
  addTimelineEvent: (event: Omit<ExecutionEvent, 'id' | 'timestamp'>) => void;
  updateMetrics: (metrics: { memoryMb?: number; cpuPercent?: number; totalTokens?: number }) => void;
  setUptime: (uptime: number) => void;
  clearLogs: () => void;
  reset: () => void;
}

/* ─── Defaults ─────────────────────────────────────────────── */

const MAX_LOGS = 500;
const MAX_TIMELINE = 100;
const MAX_TASKS = 20;

/* ─── Store ────────────────────────────────────────────────── */

let logCounter = 0;
let eventCounter = 0;

export const useAgentMonitorStore = create<AgentMonitorState>((set, get) => ({
  agentStatus: 'idle',
  activeTool: null,
  logs: [],
  currentTasks: [],
  timeline: [],
  uptime: 0,
  memoryMb: 0,
  cpuPercent: 0,
  totalTokens: 0,

  setAgentStatus: (status) => set({ agentStatus: status }),

  setActiveTool: (tool) => set({ activeTool: tool }),

  addLog: (entry) => {
    const id = `log_${Date.now()}_${++logCounter}`;
    const newEntry: LogEntry = {
      ...entry,
      id,
      timestamp: new Date().toISOString(),
    };
    set(state => {
      const logs = [...state.logs, newEntry];
      if (logs.length > MAX_LOGS) return { logs: logs.slice(-MAX_LOGS) };
      return { logs };
    });
  },

  updateTaskProgress: (taskId, updates) => {
    set(state => ({
      currentTasks: state.currentTasks.map(t =>
        t.id === taskId ? { ...t, ...updates } : t
      ),
    }));
  },

  addTask: (task) => {
    set(state => {
      const tasks = [task, ...state.currentTasks];
      if (tasks.length > MAX_TASKS) return { currentTasks: tasks.slice(0, MAX_TASKS) };
      return { currentTasks: tasks };
    });
  },

  removeTask: (taskId) => {
    set(state => ({
      currentTasks: state.currentTasks.filter(t => t.id !== taskId),
    }));
  },

  addTimelineEvent: (event) => {
    const id = `evt_${Date.now()}_${++eventCounter}`;
    const newEvent: ExecutionEvent = {
      ...event,
      id,
      timestamp: new Date().toISOString(),
    };
    set(state => {
      const timeline = [newEvent, ...state.timeline];
      if (timeline.length > MAX_TIMELINE) return { timeline: timeline.slice(0, MAX_TIMELINE) };
      return { timeline };
    });
  },

  updateMetrics: (metrics) => {
    set(state => ({
      memoryMb: metrics.memoryMb ?? state.memoryMb,
      cpuPercent: metrics.cpuPercent ?? state.cpuPercent,
      totalTokens: metrics.totalTokens ?? state.totalTokens,
    }));
  },

  setUptime: (uptime) => set({ uptime }),

  clearLogs: () => set({ logs: [] }),

  reset: () => set({
    agentStatus: 'idle',
    activeTool: null,
    logs: [],
    currentTasks: [],
    timeline: [],
  }),
}));

/* ─── Convenience helpers ──────────────────────────────────── */

export function logAgent(message: string, level: LogEntry['level'] = 'info', source = 'Agent', data?: Record<string, any>) {
  useAgentMonitorStore.getState().addLog({ level, source, message, data });
}

export function logToolCall(toolName: string, status: 'start' | 'end' | 'error', detail?: string) {
  const store = useAgentMonitorStore.getState();
  if (status === 'start') {
    store.setActiveTool({
      name: toolName,
      startedAt: new Date().toISOString(),
      duration: 0,
      status: 'running',
    });
    store.addTimelineEvent({ type: 'tool_start', label: `🔧 ${toolName}`, detail });
    store.addLog({ level: 'info', source: 'Tool', message: `▶ ${toolName} ${detail ? `— ${detail}` : ''}` });
  } else if (status === 'end') {
    store.setActiveTool(null);
    store.addTimelineEvent({ type: 'tool_end', label: `✅ ${toolName}`, detail });
    store.addLog({ level: 'success', source: 'Tool', message: `✓ ${toolName} 완료 ${detail ? `— ${detail}` : ''}` });
  } else {
    store.setActiveTool(null);
    store.setAgentStatus('error');
    store.addTimelineEvent({ type: 'error', label: `❌ ${toolName}`, detail });
    store.addLog({ level: 'error', source: 'Tool', message: `✕ ${toolName} 실패: ${detail || 'Unknown error'}` });
  }
}
