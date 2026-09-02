/**
 * TerminalSession — Individual xterm.js terminal with WebSocket
 * ==============================================================
 * Manages a single terminal session connected to backend via WebSocket.
 * Composed by MultiTerminalPanel for multi-tab terminal support.
 */

import React, { useEffect, useRef } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { readStoredAccessToken } from '../../utils/accessPinCredential';
import 'xterm/css/xterm.css';

interface Props {
  sessionId: string;
}

const TerminalSession: React.FC<Props> = ({ sessionId }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!terminalRef.current || termInstanceRef.current) return;

    let term: Terminal | null = null;
    let fitTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;
    let dataDisposable: { dispose: () => void } | null = null;
    let resizeDisposable: { dispose: () => void } | null = null;

    const handleResize = () => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();
      }
    };

    const initFrame = requestAnimationFrame(() => {
      const container = terminalRef.current;
      if (!container || termInstanceRef.current) return;

      term = new Terminal({
        theme: {
          background: '#0f1117',
          foreground: '#f3f4f6',
          cursor: '#7c6aef',
          cursorAccent: '#7c6aef',
          selectionBackground: '#3b4261',
          black: '#1a1b2e',
          red: '#f7768e',
          green: '#9ece6a',
          yellow: '#e0af68',
          blue: '#7aa2f7',
          magenta: '#bb9af7',
          cyan: '#7dcfff',
          white: '#c0caf5',
          brightBlack: '#565f89',
          brightRed: '#f7768e',
          brightGreen: '#9ece6a',
          brightYellow: '#e0af68',
          brightBlue: '#7aa2f7',
          brightMagenta: '#bb9af7',
          brightCyan: '#7dcfff',
          brightWhite: '#c0caf5',
        },
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 13,
        cursorBlink: true,
        allowTransparency: true,
      });

      const fitAddon = new FitAddon();
      termInstanceRef.current = term;
      fitAddonRef.current = fitAddon;
      term.loadAddon(fitAddon);
      term.open(container);
      fitAddon.fit();

      dataDisposable = term.onData((data: string) => {
        const ws = wsRef.current;
        if (ws?.readyState === WebSocket.OPEN) ws.send(data);
      });
      resizeDisposable = term.onResize((size: { cols: number; rows: number }) => {
        const ws = wsRef.current;
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', cols: size.cols, rows: size.rows }));
        }
      });

      const connectWebSocket = () => {
        if (disposed) return;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.port === '5173' || window.location.port === '5174' || window.location.port === '3000'
          ? 'localhost:8000' : window.location.host;
        const wsUrl = new URL(`${protocol}//${host}/ws/terminal`);
        const accessToken = readStoredAccessToken();

        const ws = accessToken === null
          ? new WebSocket(wsUrl)
          : new WebSocket(wsUrl, [`bearer.${accessToken}`]);
        wsRef.current = ws;

        ws.onopen = () => {
          if (disposed) {
            ws.close();
            return;
          }
          term?.writeln('\x1b[32m[Antigravity-K] Terminal connected.\x1b[0m');
          fitAddonRef.current?.fit();
        };

        ws.onmessage = (event: MessageEvent) => {
          if (!disposed) term?.write(event.data);
        };

        ws.onclose = (event) => {
          if (disposed) return;
          if (event.code === 1008 && event.reason === 'Terminal WebSocket is disabled') {
            term?.writeln('\x1b[33m[Antigravity-K] Terminal is disabled. Set AGK_ENABLE_TERMINAL_WS=true to enable it.\x1b[0m');
            return;
          }
          term?.writeln('\x1b[31m[Antigravity-K] Terminal disconnected. Reconnecting in 3s...\x1b[0m');
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectWebSocket();
          }, 3000);
          reconnectTimerRef.current = reconnectTimer;
        };

        ws.onerror = () => {
          if (!disposed) console.error('Terminal WebSocket error:', sessionId);
        };
      };

      connectWebSocket();
      window.addEventListener('resize', handleResize);
      fitTimer = setTimeout(() => fitAddon.fit(), 100);
    });

    return () => {
      cancelAnimationFrame(initFrame);
      disposed = true;
      window.removeEventListener('resize', handleResize);
      if (fitTimer !== null) clearTimeout(fitTimer);
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      if (reconnectTimerRef.current !== null) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
      wsRef.current = null;
      dataDisposable?.dispose();
      resizeDisposable?.dispose();
      term?.dispose();
      if (termInstanceRef.current === term) {
        termInstanceRef.current = null;
        fitAddonRef.current = null;
      }
    };
  }, [sessionId]);

  return (
    <div
      className="terminal-container"
      ref={terminalRef}
      style={{
        width: '100%',
        height: '100%',
        background: '#0f1117',
      }}
    />
  );
};

export default TerminalSession;
