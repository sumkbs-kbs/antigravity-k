/**
 * uiStore Tests
 * ==============
 * Tests for the Zustand UI store — system status, modals, toasts, folder browser.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useUiStore } from '../uiStore';

// CR-10: 미관측 상태는 0/false가 아니라 null/'unknown'이다.
const DEFAULT_SYSTEM_STATUS = {
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
  state: 'unknown' as const,
};

beforeEach(() => {
  useUiStore.setState({
    systemStatus: { ...DEFAULT_SYSTEM_STATUS },
    pinModalVisible: false,
    toasts: [],
    folderBrowserVisible: false,
    workspacePath: '/',
  });
});

describe('useUiStore', () => {
  /* ─── systemStatus ─────────────────────────────────────── */

  it('starts with UNKNOWN system status (not healthy, not zero)', () => {
    const status = useUiStore.getState().systemStatus;
    expect(status.healthy).toBeNull();
    expect(status.state).toBe('unknown');
    expect(status.observedAt).toBeNull();
    expect(status.cpuPercent).toBeNull();
    expect(status.version).toBeNull();
  });

  it('updates system status with live API values', () => {
    useUiStore.getState().setSystemStatus({
      healthy: true,
      cpuPercent: 45,
      memoryPercent: 41.5,
      version: '0.1.0',
      uptimeSeconds: 900,
      processId: 4242,
      state: 'live',
      observedAt: 1_700_000_000_000,
      backends: { search: true },
    });

    const status = useUiStore.getState().systemStatus;
    expect(status.healthy).toBe(true);
    expect(status.cpuPercent).toBe(45);
    expect(status.memoryPercent).toBe(41.5);
    expect(status.version).toBe('0.1.0');
    expect(status.uptimeSeconds).toBe(900);
    expect(status.processId).toBe(4242);
    expect(status.state).toBe('live');
    expect(status.backends).toEqual({ search: true });
  });

  it('partial update merges into existing status', () => {
    useUiStore.getState().setSystemStatus({ healthy: true, cpuPercent: 50 });
    useUiStore.getState().setSystemStatus({ memoryPercent: 41.5 });

    const status = useUiStore.getState().systemStatus;
    expect(status.healthy).toBe(true);
    expect(status.cpuPercent).toBe(50);
    expect(status.memoryPercent).toBe(41.5);
  });

  it('disconnect clears the health claim without faking zero', () => {
    useUiStore.getState().setSystemStatus({ healthy: true, cpuPercent: 12, state: 'live', observedAt: 1 });
    useUiStore.getState().setSystemStatus({ healthy: null, state: 'disconnected' });

    const status = useUiStore.getState().systemStatus;
    expect(status.healthy).toBeNull();
    expect(status.state).toBe('disconnected');
    // 마지막 성공 관측 시각은 보존되어 화면이 "언제 기준 값인지"를 말할 수 있다.
    expect(status.observedAt).toBe(1);
  });

  /* ─── Pin Modal ────────────────────────────────────────── */

  it('starts with pin modal hidden', () => {
    expect(useUiStore.getState().pinModalVisible).toBe(false);
  });

  it('shows pin modal', () => {
    useUiStore.getState().setPinModalVisible(true);
    expect(useUiStore.getState().pinModalVisible).toBe(true);
  });

  it('hides pin modal', () => {
    useUiStore.getState().setPinModalVisible(true);
    useUiStore.getState().setPinModalVisible(false);
    expect(useUiStore.getState().pinModalVisible).toBe(false);
  });

  /* ─── Toasts ───────────────────────────────────────────── */

  it('starts with empty toasts', () => {
    expect(useUiStore.getState().toasts).toHaveLength(0);
  });

  it('adds a toast with message and type', () => {
    useUiStore.getState().addToast('Hello', 'success');

    const toasts = useUiStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe('Hello');
    expect(toasts[0].type).toBe('success');
  });

  it('generates unique IDs for each toast', () => {
    useUiStore.getState().addToast('A', 'info');
    useUiStore.getState().addToast('B', 'error');

    const ids = useUiStore.getState().toasts.map(t => t.id);
    expect(ids[0]).not.toBe(ids[1]);
  });

  it('sets a removal timer for toasts', () => {
    vi.useFakeTimers();
    useUiStore.getState().addToast('Timed out', 'info');

    vi.advanceTimersByTime(3000);

    expect(useUiStore.getState().toasts).toHaveLength(0);
    vi.useRealTimers();
  });

  it('removes a toast by id', () => {
    useUiStore.getState().addToast('First', 'info');
    const id = useUiStore.getState().toasts[0].id;

    useUiStore.getState().addToast('Second', 'info');
    useUiStore.getState().removeToast(id);

    const remaining = useUiStore.getState().toasts;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].message).toBe('Second');
  });

  /* ─── Folder Browser ───────────────────────────────────── */

  it('starts with folder browser hidden', () => {
    expect(useUiStore.getState().folderBrowserVisible).toBe(false);
  });

  it('shows folder browser', () => {
    useUiStore.getState().setFolderBrowserVisible(true);
    expect(useUiStore.getState().folderBrowserVisible).toBe(true);
  });

  it('hides folder browser', () => {
    useUiStore.getState().setFolderBrowserVisible(true);
    useUiStore.getState().setFolderBrowserVisible(false);
    expect(useUiStore.getState().folderBrowserVisible).toBe(false);
  });

  /* ─── Workspace Path ───────────────────────────────────── */

  it('starts with workspace path at root', () => {
    expect(useUiStore.getState().workspacePath).toBe('/');
  });

  it('sets workspace path', () => {
    useUiStore.getState().setWorkspacePath('/home/project');
    expect(useUiStore.getState().workspacePath).toBe('/home/project');
  });

  /* ─── Mode ─────────────────────────────────────────────── */

  it('starts in interactive mode', () => {
    expect(useUiStore.getState().mode).toBe('interactive');
  });

  it('switches to plan mode', () => {
    useUiStore.getState().setMode('plan');
    expect(useUiStore.getState().mode).toBe('plan');
  });

  it('switches to build mode', () => {
    useUiStore.getState().setMode('build');
    expect(useUiStore.getState().mode).toBe('build');
  });
});
