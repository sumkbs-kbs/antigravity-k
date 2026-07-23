/**
 * MultiTerminalPanel — Multi-tab terminal with add/close/tab switching
 * =====================================================================
 * Renders a tab bar on top and the active TerminalSession below.
 * Replaces the old single TerminalPanel.
 */
// @ts-nocheck


import React, { useEffect, useRef } from 'react';
import TerminalSession from './TerminalSession';
import { useTerminalStore } from '../../stores/terminalStore';

const MultiTerminalPanel: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    addSession,
    closeSession,
    setActiveSession,
  } = useTerminalStore();

  const hasInitialized = useRef(false);

  // Auto-add first terminal on initial render
  useEffect(() => {
    if (!hasInitialized.current && sessions.length === 0) {
      hasInitialized.current = true;
      addSession();
    }
  }, [sessions.length, addSession]);

  return (
    <div className="multi-terminal">
      {/* ── Tab Bar ────────────────────────────────────────── */}
      <div className="multi-terminal-tabs">
        <div className="terminal-tabs-scroll">
          {sessions.map(session => (
            <div
              key={session.id}
              className={`terminal-tab ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => setActiveSession(session.id)}
              title={`Terminal: ${session.name}`}
            >
              <span className="terminal-tab-icon">💻</span>
              <span className="terminal-tab-name">{session.name}</span>
              <button
                className="terminal-tab-close"
                onClick={e => { e.stopPropagation(); closeSession(session.id); }}
                title="Close terminal"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <button
          className="terminal-add-btn"
          onClick={() => addSession()}
          title="New terminal"
        >
          +
        </button>
      </div>

      {/* ── Terminal Content Area ──────────────────────────── */}
      <div className="multi-terminal-content">
        {sessions.length === 0 ? (
          <div className="terminal-empty" onClick={() => addSession()}>
            <span className="terminal-empty-icon">💻</span>
            <span className="terminal-empty-text">Click to open a new terminal</span>
          </div>
        ) : (
          sessions.map(session => (
            <div
              key={session.id}
              className={`terminal-session-wrapper ${session.id === activeSessionId ? 'active' : ''}`}
            >
              <TerminalSession sessionId={session.id} />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default MultiTerminalPanel;
