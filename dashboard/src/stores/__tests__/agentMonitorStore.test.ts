/**
 * agentMonitorStore Tests
 * ========================
 * Tests for the Zustand agent monitor store — agent status, log stream,
 * task progress, timeline events, system metrics, convenience helpers.
 * Phase 7 (Agent Monitoring Dashboard) core functionality.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  useAgentMonitorStore,
  logAgent,
  logToolCall,
  type AgentStatus,
  type ActiveTool,
  type TaskProgress,
  type ExecutionEvent,
} from '../agentMonitorStore';

beforeEach(() => {
  useAgentMonitorStore.setState({
    agentStatus: 'idle',
    activeTool: null,
    logs: [],
    currentTasks: [],
    timeline: [],
    uptime: 0,
    memoryMb: 0,
    cpuPercent: 0,
    totalTokens: 0,
  });
});

describe('useAgentMonitorStore', () => {
  /* ─── Initial State ─────────────────────────────────────── */

  it('starts with default state', () => {
    const state = useAgentMonitorStore.getState();
    expect(state.agentStatus).toBe('idle');
    expect(state.activeTool).toBeNull();
    expect(state.logs).toHaveLength(0);
    expect(state.currentTasks).toHaveLength(0);
    expect(state.timeline).toHaveLength(0);
    expect(state.uptime).toBe(0);
    expect(state.memoryMb).toBe(0);
    expect(state.cpuPercent).toBe(0);
    expect(state.totalTokens).toBe(0);
  });

  /* ─── setAgentStatus ────────────────────────────────────── */

  it('sets agent status to all valid values', () => {
    const statuses: AgentStatus[] = ['idle', 'running', 'planning', 'error', 'thinking'];
    for (const s of statuses) {
      useAgentMonitorStore.getState().setAgentStatus(s);
      expect(useAgentMonitorStore.getState().agentStatus).toBe(s);
    }
  });

  /* ─── setActiveTool ─────────────────────────────────────── */

  it('sets active tool', () => {
    const tool: ActiveTool = {
      name: 'web_search',
      startedAt: new Date().toISOString(),
      duration: 0,
      status: 'running',
    };

    useAgentMonitorStore.getState().setActiveTool(tool);
    expect(useAgentMonitorStore.getState().activeTool).toEqual(tool);
  });

  it('clears active tool to null', () => {
    useAgentMonitorStore.getState().setActiveTool({
      name: 'search', startedAt: 'now', duration: 5, status: 'running',
    });
    useAgentMonitorStore.getState().setActiveTool(null);

    expect(useAgentMonitorStore.getState().activeTool).toBeNull();
  });

  /* ─── addLog ────────────────────────────────────────────── */

  it('adds a log entry with generated id and timestamp', () => {
    useAgentMonitorStore.getState().addLog({
      level: 'info',
      source: 'Tool',
      message: 'Search started',
    });

    const log = useAgentMonitorStore.getState().logs[0];
    expect(log.message).toBe('Search started');
    expect(log.level).toBe('info');
    expect(log.source).toBe('Tool');
    expect(log.id).toMatch(/^log_/);
    expect(log.timestamp).toBeDefined();
  });

  it('adds a log entry with data', () => {
    useAgentMonitorStore.getState().addLog({
      level: 'error',
      source: 'System',
      message: 'Error occurred',
      data: { code: 500, reason: 'timeout' },
    });

    expect(useAgentMonitorStore.getState().logs[0].data).toEqual({ code: 500, reason: 'timeout' });
  });

  it('maintains log entry order', () => {
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'A', message: 'First' });
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'B', message: 'Second' });

    const messages = useAgentMonitorStore.getState().logs.map(l => l.message);
    expect(messages).toEqual(['First', 'Second']);
  });

  it('supports all log levels', () => {
    const levels = ['info', 'warn', 'error', 'debug', 'success'] as const;
    levels.forEach(lvl => {
      useAgentMonitorStore.getState().addLog({ level: lvl, source: 'Test', message: `Level: ${lvl}` });
    });

    expect(useAgentMonitorStore.getState().logs).toHaveLength(5);
  });

  it('trims logs when exceeding max (ring buffer)', () => {
    // Add many logs to trigger ring buffer trim (MAX_LOGS = 500)
    for (let i = 0; i < 600; i++) {
      useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: `Log ${i}` });
    }

    expect(useAgentMonitorStore.getState().logs.length).toBeLessThanOrEqual(500);
  });

  /* ─── updateTaskProgress ─────────────────────────────────- */

  it('updates a task progress by id', () => {
    const task: TaskProgress = {
      id: 'task-1', title: 'Search', status: 'running', progress: 30,
    };
    useAgentMonitorStore.getState().addTask(task);

    useAgentMonitorStore.getState().updateTaskProgress('task-1', {
      progress: 80,
      status: 'completed',
    });

    const updated = useAgentMonitorStore.getState().currentTasks[0];
    expect(updated.progress).toBe(80);
    expect(updated.status).toBe('completed');
    expect(updated.title).toBe('Search'); // unchanged
  });

  it('does nothing for non-existent task id', () => {
    useAgentMonitorStore.getState().updateTaskProgress('nonexistent', { progress: 50 });
    expect(useAgentMonitorStore.getState().currentTasks).toHaveLength(0);
  });

  /* ─── addTask / removeTask ──────────────────────────────── */

  it('adds a task to the beginning of the list', () => {
    useAgentMonitorStore.getState().addTask({
      id: 't1', title: 'First task', status: 'running', progress: 0,
    });

    expect(useAgentMonitorStore.getState().currentTasks).toHaveLength(1);
    expect(useAgentMonitorStore.getState().currentTasks[0].title).toBe('First task');
  });

  it('prepends newer tasks', () => {
    useAgentMonitorStore.getState().addTask({
      id: 't1', title: 'Old', status: 'running', progress: 50,
    });
    useAgentMonitorStore.getState().addTask({
      id: 't2', title: 'New', status: 'queued', progress: 0,
    });

    expect(useAgentMonitorStore.getState().currentTasks[0].title).toBe('New');
  });

  it('removes a task by id', () => {
    useAgentMonitorStore.getState().addTask({ id: 't1', title: 'A', status: 'running', progress: 0 });
    useAgentMonitorStore.getState().addTask({ id: 't2', title: 'B', status: 'running', progress: 0 });

    useAgentMonitorStore.getState().removeTask('t1');

    expect(useAgentMonitorStore.getState().currentTasks).toHaveLength(1);
    expect(useAgentMonitorStore.getState().currentTasks[0].id).toBe('t2');
  });

  it('trims tasks when exceeding max (MAX_TASKS = 20)', () => {
    for (let i = 0; i < 25; i++) {
      useAgentMonitorStore.getState().addTask({
        id: `t${i}`, title: `Task ${i}`, status: 'running', progress: i * 10,
      });
    }

    expect(useAgentMonitorStore.getState().currentTasks.length).toBeLessThanOrEqual(20);
  });

  /* ─── addTimelineEvent ──────────────────────────────────── */

  it('adds a timeline event with generated id and timestamp', () => {
    useAgentMonitorStore.getState().addTimelineEvent({
      type: 'tool_start',
      label: '🔧 search',
      detail: 'Searching web',
    });

    const event = useAgentMonitorStore.getState().timeline[0];
    expect(event.label).toBe('🔧 search');
    expect(event.type).toBe('tool_start');
    expect(event.detail).toBe('Searching web');
    expect(event.id).toMatch(/^evt_/);
    expect(event.timestamp).toBeDefined();
  });

  it('prepends new events to the timeline', () => {
    useAgentMonitorStore.getState().addTimelineEvent({ type: 'plan', label: 'Planned' });
    useAgentMonitorStore.getState().addTimelineEvent({ type: 'tool_start', label: 'Executed' });

    expect(useAgentMonitorStore.getState().timeline[0].label).toBe('Executed');
    expect(useAgentMonitorStore.getState().timeline[1].label).toBe('Planned');
  });

  it('supports all timeline event types', () => {
    const types: ExecutionEvent['type'][] = [
      'tool_start', 'tool_end', 'task_start', 'task_end',
      'error', 'plan', 'mode_change',
    ];
    types.forEach(type => {
      useAgentMonitorStore.getState().addTimelineEvent({ type, label: `Event: ${type}` });
    });

    expect(useAgentMonitorStore.getState().timeline).toHaveLength(7);
  });

  it('trims timeline when exceeding max (MAX_TIMELINE = 100)', () => {
    for (let i = 0; i < 120; i++) {
      useAgentMonitorStore.getState().addTimelineEvent({ type: 'plan', label: `Event ${i}` });
    }

    expect(useAgentMonitorStore.getState().timeline.length).toBeLessThanOrEqual(100);
  });

  /* ─── updateMetrics ─────────────────────────────────────── */

  it('updates metrics with partial values', () => {
    useAgentMonitorStore.getState().updateMetrics({ memoryMb: 2048, cpuPercent: 45 });

    expect(useAgentMonitorStore.getState().memoryMb).toBe(2048);
    expect(useAgentMonitorStore.getState().cpuPercent).toBe(45);
    expect(useAgentMonitorStore.getState().totalTokens).toBe(0); // unchanged
  });

  it('updates metrics with all values', () => {
    useAgentMonitorStore.getState().updateMetrics({ memoryMb: 4096, cpuPercent: 80, totalTokens: 15000 });

    expect(useAgentMonitorStore.getState().memoryMb).toBe(4096);
    expect(useAgentMonitorStore.getState().cpuPercent).toBe(80);
    expect(useAgentMonitorStore.getState().totalTokens).toBe(15000);
  });

  it('only updates provided metrics (partial merge)', () => {
    useAgentMonitorStore.getState().updateMetrics({ totalTokens: 5000 });

    expect(useAgentMonitorStore.getState().memoryMb).toBe(0);
    expect(useAgentMonitorStore.getState().cpuPercent).toBe(0);
    expect(useAgentMonitorStore.getState().totalTokens).toBe(5000);
  });

  /* ─── setUptime ─────────────────────────────────────────── */

  it('sets uptime', () => {
    useAgentMonitorStore.getState().setUptime(3600);
    expect(useAgentMonitorStore.getState().uptime).toBe(3600);
  });

  /* ─── clearLogs ─────────────────────────────────────────── */

  it('clears all logs', () => {
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: 'Log entry' });
    useAgentMonitorStore.getState().clearLogs();

    expect(useAgentMonitorStore.getState().logs).toHaveLength(0);
  });

  /* ─── reset ─────────────────────────────────────────────── */

  it('resets to default state', () => {
    useAgentMonitorStore.getState().setAgentStatus('running');
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: 'Log' });
    useAgentMonitorStore.getState().addTask({ id: 't1', title: 'Task', status: 'running', progress: 0 });
    useAgentMonitorStore.getState().addTimelineEvent({ type: 'plan', label: 'Plan' });

    useAgentMonitorStore.getState().reset();

    const state = useAgentMonitorStore.getState();
    expect(state.agentStatus).toBe('idle');
    expect(state.activeTool).toBeNull();
    expect(state.logs).toHaveLength(0);
    expect(state.currentTasks).toHaveLength(0);
    expect(state.timeline).toHaveLength(0);
  });

    /* ─── addLog: Edge Cases ────────────────────────────────── */

  it('trims to exactly 500 logs when adding 501 (exact boundary)', () => {
    for (let i = 0; i < 501; i++) {
      useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: `Log ${i}` });
    }

    const logs = useAgentMonitorStore.getState().logs;
    expect(logs.length).toBe(500);
    // The 501st log (last added) should be present (newest preserved)
    expect(logs[logs.length - 1].message).toBe('Log 500');
    // The 1st log should be trimmed (oldest removed)
    expect(logs[0].message).toBe('Log 1');
  });

  it('preserves newest logs when trimming (slice direction)', () => {
    for (let i = 0; i < 550; i++) {
      useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: `Log ${i}` });
    }

    const messages = useAgentMonitorStore.getState().logs.map(l => l.message);
    // Should keep the LAST 500 logs (newest), not the FIRST 500
    expect(messages[0]).toBe('Log 50');
    expect(messages[messages.length - 1]).toBe('Log 549');
  });

  it('increments log counter across sequential calls', () => {
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'A', message: 'First' });
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'B', message: 'Second' });

    const logs = useAgentMonitorStore.getState().logs;
    expect(logs[0].id).toMatch(/^log_\d+_\d+$/);
    expect(logs[1].id).toMatch(/^log_\d+_\d+$/);
    // IDs should be different (counter incremented)
    expect(logs[0].id).not.toBe(logs[1].id);
  });

  /* ─── addTask: Edge Cases ───────────────────────────────── */

  it('trims to exactly 20 tasks when adding 21 (exact boundary)', () => {
    for (let i = 0; i < 21; i++) {
      useAgentMonitorStore.getState().addTask({
        id: `t${i}`, title: `Task ${i}`, status: 'running', progress: 0,
      });
    }

    const tasks = useAgentMonitorStore.getState().currentTasks;
    expect(tasks.length).toBe(20);
    // 21st task (newest) should be present
    expect(tasks[0].title).toBe('Task 20');
    // Oldest task should be trimmed
    expect(tasks[tasks.length - 1].title).toBe('Task 1');
  });

  it('prepends newest tasks and trims oldest from the end', () => {
    for (let i = 0; i < 30; i++) {
      useAgentMonitorStore.getState().addTask({
        id: `t${i}`, title: `Task ${i}`, status: 'running', progress: i * 10,
      });
    }

    const tasks = useAgentMonitorStore.getState().currentTasks;
    // Newest at index 0, oldest trimmed from end
    expect(tasks[0].title).toBe('Task 29');
    expect(tasks[tasks.length - 1].title).toBe('Task 10');
    expect(tasks.length).toBe(20);
  });

  /* ─── addTimelineEvent: Edge Cases ───────────────────────── */

  it('trims to exactly 100 events when adding 101 (exact boundary)', () => {
    for (let i = 0; i < 101; i++) {
      useAgentMonitorStore.getState().addTimelineEvent({ type: 'plan', label: `Event ${i}` });
    }

    const events = useAgentMonitorStore.getState().timeline;
    expect(events.length).toBe(100);
    // 101st event (newest) should be present at beginning
    expect(events[0].label).toBe('Event 100');
  });

  it('prepends newest events to timeline (LIFO order)', () => {
    useAgentMonitorStore.getState().addTimelineEvent({ type: 'plan', label: 'Earliest' });
    useAgentMonitorStore.getState().addTimelineEvent({ type: 'tool_start', label: 'Middle' });
    useAgentMonitorStore.getState().addTimelineEvent({ type: 'tool_end', label: 'Latest' });

    const events = useAgentMonitorStore.getState().timeline;
    expect(events[0].label).toBe('Latest');
    expect(events[1].label).toBe('Middle');
    expect(events[2].label).toBe('Earliest');
  });

  /* ─── updateMetrics: Edge Cases ──────────────────────────── */

  it('preserves existing value when metric is null', () => {
    useAgentMonitorStore.getState().updateMetrics({ memoryMb: 1024, cpuPercent: 50, totalTokens: 1000 });
    // Update with null value — should keep existing
    useAgentMonitorStore.getState().updateMetrics({ memoryMb: null as any, cpuPercent: undefined, totalTokens: 2000 });

    const state = useAgentMonitorStore.getState();
    // null should NOT override (?? preserves for null/undefined)
    expect(state.memoryMb).toBe(1024);
    // undefined should NOT override
    expect(state.cpuPercent).toBe(50);
    // valid value SHOULD override
    expect(state.totalTokens).toBe(2000);
  });

  it('overrides metric with zero values', () => {
    useAgentMonitorStore.getState().updateMetrics({ memoryMb: 2048 });
    useAgentMonitorStore.getState().updateMetrics({ memoryMb: 0 });

    expect(useAgentMonitorStore.getState().memoryMb).toBe(0);
  });

  /* ─── reset: Edge Cases ──────────────────────────────────── */

  it('resets non-persistent state fields to defaults', () => {
    // Set non-persistent fields to non-default values
    useAgentMonitorStore.getState().setAgentStatus('running');
    useAgentMonitorStore.getState().setActiveTool({ name: 'test', startedAt: 'now', duration: 5, status: 'running' });
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: 'Log' });
    useAgentMonitorStore.getState().addTask({ id: 't1', title: 'T', status: 'running', progress: 0 });
    useAgentMonitorStore.getState().addTimelineEvent({ type: 'plan', label: 'P' });

    useAgentMonitorStore.getState().reset();

    const state = useAgentMonitorStore.getState();
    expect(state.agentStatus).toBe('idle');
    expect(state.activeTool).toBeNull();
    expect(state.logs).toHaveLength(0);
    expect(state.currentTasks).toHaveLength(0);
    expect(state.timeline).toHaveLength(0);
    // uptime/metrics are intentionally preserved across resets
  });

  /* ─── Edge Case: Precondition Checks ( > vs >= mutants ) ─── */

  it('does not trigger log trim at exactly MAX_LOGS boundary', () => {
    // Add exactly 500 logs (MAX_LOGS). Condition should be FALSE for > (no trim).
    for (let i = 0; i < 500; i++) {
      useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: `Log ${i}` });
    }
    expect(useAgentMonitorStore.getState().logs.length).toBe(500);

    // Add 1 more — trim should trigger
    useAgentMonitorStore.getState().addLog({ level: 'info', source: 'Test', message: 'Overflow' });
    expect(useAgentMonitorStore.getState().logs.length).toBe(500);
  });

  it('does not trigger task trim at exactly MAX_TASKS boundary', () => {
    for (let i = 0; i < 20; i++) {
      useAgentMonitorStore.getState().addTask({
        id: `t${i}`, title: `T${i}`, status: 'running', progress: 0,
      });
    }
    expect(useAgentMonitorStore.getState().currentTasks.length).toBe(20);

    useAgentMonitorStore.getState().addTask({ id: 'overflow', title: 'Overflow', status: 'running', progress: 0 });
    expect(useAgentMonitorStore.getState().currentTasks.length).toBe(20);
  });

  it('does not trigger timeline trim at exactly MAX_TIMELINE boundary', () => {
    for (let i = 0; i < 100; i++) {
      useAgentMonitorStore.getState().addTimelineEvent({ type: 'plan', label: `E${i}` });
    }
    expect(useAgentMonitorStore.getState().timeline.length).toBe(100);

    useAgentMonitorStore.getState().addTimelineEvent({ type: 'tool_start', label: 'Overflow' });
    expect(useAgentMonitorStore.getState().timeline.length).toBe(100);
  });

  /* ─── Convenience Helpers ───────────────────────────────── */

  it('logAgent adds a log entry', () => {
    logAgent('Agent starting', 'info', 'Agent', { mode: 'plan' });

    const log = useAgentMonitorStore.getState().logs[0];
    expect(log.message).toBe('Agent starting');
    expect(log.level).toBe('info');
    expect(log.source).toBe('Agent');
    expect(log.data).toEqual({ mode: 'plan' });
  });

  it('logAgent uses defaults', () => {
    logAgent('Default log');

    const log = useAgentMonitorStore.getState().logs[0];
    expect(log.level).toBe('info');
    expect(log.source).toBe('Agent');
  });

  it('logToolCall with start sets active tool and adds events', () => {
    logToolCall('web_search', 'start', 'Searching query');

    const state = useAgentMonitorStore.getState();
    expect(state.activeTool).not.toBeNull();
    expect(state.activeTool!.name).toBe('web_search');
    expect(state.activeTool!.status).toBe('running');
    expect(state.timeline.length).toBeGreaterThan(0);
    expect(state.timeline[0].type).toBe('tool_start');
    expect(state.logs.length).toBeGreaterThan(0);
    expect(state.logs[0].level).toBe('info');
  });

  it('logToolCall with end clears active tool and adds events', () => {
    logToolCall('web_search', 'start');
    logToolCall('web_search', 'end', 'Completed');

    const state = useAgentMonitorStore.getState();
    expect(state.activeTool).toBeNull();
    expect(state.timeline[0].type).toBe('tool_end');
    // The last log entry (index 1) is the 'end' success log;
    // index 0 is the 'start' info log.
    expect(state.logs[1].level).toBe('success');
    expect(state.logs[1].message).toContain('✓');
  });

  it('logToolCall with error sets error status', () => {
    logToolCall('web_search', 'error', 'Connection timeout');

    const state = useAgentMonitorStore.getState();
    expect(state.activeTool).toBeNull();
    expect(state.agentStatus).toBe('error');
    expect(state.timeline[0].type).toBe('error');
    expect(state.logs[0].level).toBe('error');
  });
});
