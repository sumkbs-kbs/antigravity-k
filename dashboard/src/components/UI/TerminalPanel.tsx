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
  const visibleRef = useRef(false);

  // Listen for terminal visibility toggle from Sidebar
  const [visible, setVisible] = useState(false);

  const connectWebSocket = useCallback((term: Terminal) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5173' || window.location.port === '5174' || window.location.port === '3000'
      ? 'localhost:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/terminal`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      term.writeln('\x1b[32m[Antigravity-K] Terminal connected.\x1b[0m');

      term.onData((data: string) => {
        if (ws.readyState === WebSocket.OPEN) ws.send(data);
      });

      term.onResize((size: { cols: number; rows: number }) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', cols: size.cols, rows: size.rows }));
        }
      });

      fitAddonRef.current?.fit();
    };

    ws.onmessage = (event: MessageEvent) => {
      term.write(event.data);
    };

    ws.onclose = () => {
      term.writeln('\x1b[31m[Antigravity-K] Terminal disconnected. Reconnecting in 3s...\x1b[0m');
      setTimeout(() => {
        if (visibleRef.current) connectWebSocket(term);
      }, 3000);
    };

    ws.onerror = () => {
      console.error('Terminal WebSocket error');
    };
  }, []);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || termInstanceRef.current) return;

    const term = new Terminal({
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
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    termInstanceRef.current = term;
    fitAddonRef.current = fitAddon;

    connectWebSocket(term);

    // Resize handler
    const handleResize = () => {
      if (visibleRef.current && fitAddonRef.current) {
        fitAddonRef.current.fit();
      }
    };
    window.addEventListener('resize', handleResize);

    // Re-fit when terminal becomes visible
    const checkVisible = setInterval(() => {
      if (visibleRef.current && fitAddonRef.current) {
        fitAddonRef.current.fit();
        clearInterval(checkVisible);
      }
    }, 100);

    return () => {
      window.removeEventListener('resize', handleResize);
      clearInterval(checkVisible);
      term.dispose();
      wsRef.current?.close();
      termInstanceRef.current = null;
      fitAddonRef.current = null;
    };
  }, [connectWebSocket]);

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
  const visibleRef = useRef(false);

  const toggleTerminal = useCallback(() => {
    setTerminalVisible(prev => {
      const next = !prev;
      visibleRef.current = next;
      // Re-fit after next render
      if (next) {
        setTimeout(() => {
          const termEl = document.querySelector('.terminal-container') as HTMLElement;
          if (termEl) {
            // Trigger FitAddon via resize event
            window.dispatchEvent(new Event('resize'));
          }
        }, 50);
      }
      return next;
    });
  }, []);

  return { terminalVisible, toggleTerminal };
}

export default TerminalPanel;
