/**
 * TerminalPanel — xterm.js terminal with WebSocket
 * ==================================================
 * Ported from Vanilla JS. Provides a terminal connected to backend via WebSocket.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

const TerminalPanel: React.FC = () => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || termInstanceRef.current) return;

    let disposed = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let activeWs: WebSocket | null = null;
    let term: Terminal | null = null;
    let fitAddon: FitAddon | null = null;
    let fitTimer: ReturnType<typeof setTimeout> | null = null;
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

      fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(container);
      fitAddon.fit();
      termInstanceRef.current = term;
      fitAddonRef.current = fitAddon;

      const connectWebSocket = () => {
        if (disposed || !term || !fitAddon) return;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.port === '5173' || window.location.port === '5174' || window.location.port === '3000'
          ? 'localhost:8000' : window.location.host;
        const ws = new WebSocket(`${protocol}//${host}/ws/terminal`);
        activeWs = ws;
        wsRef.current = ws;

        ws.onopen = () => {
          if (disposed) {
            ws.close();
            return;
          }
          term?.writeln('\x1b[32m[Antigravity-K] Terminal connected.\x1b[0m');
          fitAddon?.fit();
        };
        ws.onmessage = (event: MessageEvent) => {
          if (!disposed) term?.write(event.data);
        };
        ws.onclose = () => {
          if (disposed) return;
          term?.writeln('\x1b[31m[Antigravity-K] Terminal disconnected. Reconnecting in 3s...\x1b[0m');
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectWebSocket();
          }, 3000);
        };
        ws.onerror = () => {
          if (!disposed) console.error('Terminal WebSocket error');
        };
      };

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
      connectWebSocket();
      window.addEventListener('resize', handleResize);
      fitTimer = setTimeout(() => fitAddon?.fit(), 100);
    });

    return () => {
      disposed = true;
      cancelAnimationFrame(initFrame);
      window.removeEventListener('resize', handleResize);
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      if (fitTimer !== null) clearTimeout(fitTimer);
      dataDisposable?.dispose();
      resizeDisposable?.dispose();
      term?.dispose();
      if (activeWs) {
        activeWs.onclose = null;
        activeWs.close();
        activeWs = null;
      }
      wsRef.current = null;
      termInstanceRef.current = null;
      fitAddonRef.current = null;
    };
  }, []);

  return (
    <div
      id="terminal-container"
      className="terminal-container"
      ref={terminalRef}
      role="application"
      aria-label="터미널"
      style={{
        width: '100%',
        height: '100%',
        background: '#0f1117',
      }}
    />
  );
};

/** Terminal toggle hook — returns toggle function and visibility state */
export function useTerminalToggle() {
  const [terminalVisible, setTerminalVisible] = useState(false);

  const toggleTerminal = useCallback(() => {
    setTerminalVisible(prev => !prev);
  }, []);

  useEffect(() => {
    if (!terminalVisible) return undefined;
    const resizeTimer = setTimeout(() => {
      if (document.querySelector('.terminal-container')) {
        window.dispatchEvent(new Event('resize'));
      }
    }, 50);
    return () => clearTimeout(resizeTimer);
  }, [terminalVisible]);

  return { terminalVisible, toggleTerminal };
}

export default TerminalPanel;
