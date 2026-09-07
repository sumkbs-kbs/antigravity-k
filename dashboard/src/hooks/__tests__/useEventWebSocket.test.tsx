import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { EventHandlers } from '../useEventWebSocket';
import { useEventWebSocket } from '../useEventWebSocket';
import { useUiStore } from '../../stores/uiStore';

// SEC-03: WS 인증은 장기 bearer subprotocol 대신 단기 1회성 ticket 교환이다.
// fetchWsTicket을 mock해 ticket 플로우를 결정적으로 검증한다.
vi.mock('../../utils/wsTicket', () => ({
  fetchWsTicket: vi.fn(async () => 'sec03-one-time-ticket'),
}));
import { fetchWsTicket } from '../../utils/wsTicket';

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static readonly instances: MockWebSocket[] = [];

  readonly url: string;
  readonly protocols: string[] | undefined;
  readyState = MockWebSocket.OPEN;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onopen: (() => void) | null = null;

  constructor(url: string | URL, protocols?: string | string[]) {
    this.url = url.toString();
    this.protocols = protocols === undefined ? undefined : typeof protocols === 'string' ? [protocols] : protocols;
    MockWebSocket.instances.push(this);
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }

  emitMessage(message: unknown): void {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(message) }));
  }
}

function HookHarness({ handlers }: { readonly handlers: EventHandlers }) {
  useEventWebSocket(handlers);
  return null;
}

describe('useEventWebSocket', () => {
  beforeEach(() => {
    MockWebSocket.instances.length = 0;
    localStorage.clear();
    sessionStorage.clear();
    useUiStore.setState({ mode: 'interactive' });
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('routes a valid mode event and updates the UI mode', () => {
    // Given
    const onModeChanged = vi.fn();
    render(<HookHarness handlers={{ onModeChanged }} />);
    const socket = MockWebSocket.instances.at(0);

    // When
    act(() => {
      socket?.emitMessage({ event: 'ModeChanged', data: { to_mode: 'plan' } });
    });

    // Then
    expect(onModeChanged).toHaveBeenCalledWith({ to_mode: 'plan' });
    expect(useUiStore.getState().mode).toBe('plan');
  });

  it('ignores an event whose payload does not match its contract', () => {
    // Given
    const onFailureDetected = vi.fn();
    render(<HookHarness handlers={{ onFailureDetected }} />);
    const socket = MockWebSocket.instances.at(0);

    // When
    act(() => {
      socket?.emitMessage({ event: 'FailureDetected', data: 'not-an-object' });
    });

    // Then
    expect(onFailureDetected).not.toHaveBeenCalled();
  });

  it('does not reconnect after its component unmounts', () => {
    // Given
    vi.useFakeTimers();
    const view = render(<HookHarness handlers={{}} />);

    // When
    view.unmount();
    act(() => {
      vi.advanceTimersByTime(3_000);
    });

    // Then
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('routes a quality check failed event to its handler', () => {
    // Given
    const onQualityCheckFailed = vi.fn();
    render(<HookHarness handlers={{ onQualityCheckFailed }} />);
    const socket = MockWebSocket.instances.at(0);

    // When
    act(() => {
      socket?.emitMessage({
        event: 'QualityCheckFailed',
        data: { task_type: 'plan', grade: 'retry', issues: ['불명확'], feedback: '보완 필요' },
      });
    });

    // Then
    expect(onQualityCheckFailed).toHaveBeenCalledWith({
      task_type: 'plan',
      grade: 'retry',
      issues: ['불명확'],
      feedback: '보완 필요',
    });
  });

  it('routes an anti-patterns detected event to its handler', () => {
    // Given
    const onAntiPatternsDetected = vi.fn();
    render(<HookHarness handlers={{ onAntiPatternsDetected }} />);
    const socket = MockWebSocket.instances.at(0);

    // When
    act(() => {
      socket?.emitMessage({
        event: 'AntiPatternsDetected',
        data: { reason: '반복 실패 감지', tools: ['run_bash_command'], patterns: ['timeout 발생'] },
      });
    });

    // Then
    expect(onAntiPatternsDetected).toHaveBeenCalledWith({
      reason: '반복 실패 감지',
      tools: ['run_bash_command'],
      patterns: ['timeout 발생'],
    });
  });

  it('authenticates the event websocket with a one-time ticket query param', async () => {
    // Given — SEC-03: 저장된 bearer가 있으면 /auth/ws-ticket으로 단기 ticket을
    // 교환하고, WS URL에는 ?ticket= 로 단 한 번 실린다 (subprotocol 없음).
    sessionStorage.setItem('ag_access_token', 'event-token');

    // When
    render(<HookHarness handlers={{}} />);
    await act(async () => {
      await Promise.resolve();
    });
    const socketUrl = MockWebSocket.instances.at(0)?.url;

    // Then
    expect(socketUrl).toBeDefined();
    const parsedUrl = new URL(socketUrl ?? 'ws://invalid');
    expect(parsedUrl.pathname).toBe('/v1/ws/events');
    expect(parsedUrl.searchParams.get('ticket')).toBe('sec03-one-time-ticket');
    // credential이 subprotocol/다른 query로 노출되지 않는다
    expect(MockWebSocket.instances.at(0)?.protocols).toBeUndefined();
    expect(parsedUrl.searchParams.get('token')).toBeNull();
    expect(parsedUrl.searchParams.get('pin')).toBeNull();
  });

  it('connects without a ticket when no credential is stored', () => {
    // Given — 익명(open_loopback) 서버 플로우: credential이 없으면 ticket
    // 발급 자체를 시도하지 않고 곧바로 연결한다.
    vi.mocked(fetchWsTicket).mockClear();

    // When
    render(<HookHarness handlers={{}} />);
    const socketUrl = MockWebSocket.instances.at(0)?.url;

    // Then
    expect(socketUrl).toBeDefined();
    const parsedUrl = new URL(socketUrl ?? 'ws://invalid');
    expect(parsedUrl.pathname).toBe('/v1/ws/events');
    expect(parsedUrl.search).toBe('');
    expect(MockWebSocket.instances.at(0)?.protocols).toBeUndefined();
    expect(fetchWsTicket).not.toHaveBeenCalled();
  });
});
