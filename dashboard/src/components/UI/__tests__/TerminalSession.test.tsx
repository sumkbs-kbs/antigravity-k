import React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const terminalMocks = vi.hoisted(() => ({
  dispose: vi.fn(),
  fit: vi.fn(),
  loadAddon: vi.fn(),
  onData: vi.fn(),
  onResize: vi.fn(),
  open: vi.fn(),
  write: vi.fn(),
  writeln: vi.fn(),
}));

vi.mock('xterm', () => ({
  Terminal: class Terminal {
    dispose = terminalMocks.dispose;
    loadAddon = terminalMocks.loadAddon;
    onData = terminalMocks.onData;
    onResize = terminalMocks.onResize;
    open = terminalMocks.open;
    write = terminalMocks.write;
    writeln = terminalMocks.writeln;
  },
}));

vi.mock('xterm-addon-fit', () => ({
  FitAddon: class FitAddon {
    fit = terminalMocks.fit;
  },
}));

import TerminalSession from '../TerminalSession';

class MockWebSocket {
  static readonly OPEN = 1;
  static readonly instances: MockWebSocket[] = [];

  readonly url: string;
  readonly readyState = MockWebSocket.OPEN;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;

  constructor(url: string | URL) {
    this.url = url.toString();
    MockWebSocket.instances.push(this);
  }

  close() {}
  send() {}
}

describe('TerminalSession', () => {
  const frames = new Map<number, FrameRequestCallback>();
  let nextFrameId = 0;

  beforeEach(() => {
    frames.clear();
    nextFrameId = 0;
    MockWebSocket.instances.length = 0;
    localStorage.clear();
    Object.values(terminalMocks).forEach(mock => mock.mockClear());
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      const frameId = ++nextFrameId;
      frames.set(frameId, callback);
      return frameId;
    });
    vi.stubGlobal('cancelAnimationFrame', (frameId: number) => {
      frames.delete(frameId);
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('opens one xterm instance during a normal mount', () => {
    render(<TerminalSession sessionId="terminal-test" />);

    act(() => {
      [...frames.values()].forEach(callback => callback(0));
    });

    expect(terminalMocks.open).toHaveBeenCalledTimes(1);
    expect(terminalMocks.fit).toHaveBeenCalledTimes(1);
  });

  it('opens one xterm instance after a StrictMode remount', () => {
    render(
      <React.StrictMode>
        <TerminalSession sessionId="terminal-test" />
      </React.StrictMode>,
    );

    act(() => {
      [...frames.values()].forEach(callback => callback(0));
    });

    expect(terminalMocks.open).toHaveBeenCalledTimes(1);
    expect(terminalMocks.fit).toHaveBeenCalledTimes(1);
  });

  it('authenticates the terminal websocket with the stored PIN', () => {
    localStorage.setItem('ag_access_pin', 'terminal pin');
    render(<TerminalSession sessionId="terminal-test" />);

    act(() => {
      [...frames.values()].forEach(callback => callback(0));
    });

    expect(MockWebSocket.instances[0]?.url).toBe('ws://localhost:8000/ws/terminal?pin=terminal+pin');
  });

  it('does not reconnect when the terminal feature is disabled', () => {
    render(<TerminalSession sessionId="terminal-test" />);

    act(() => {
      [...frames.values()].forEach(callback => callback(0));
    });

    const timeoutSpy = vi.spyOn(window, 'setTimeout');
    act(() => {
      MockWebSocket.instances[0]?.onclose?.(new CloseEvent('close', {
        code: 1008,
        reason: 'Terminal WebSocket is disabled',
      }));
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(terminalMocks.writeln).toHaveBeenCalledWith(expect.stringContaining('disabled'));
    expect(timeoutSpy).not.toHaveBeenCalled();
  });
});
