/**
 * MultiTerminalPanel — Multi-tab terminal with add/close/tab switching
 * =====================================================================
 * Renders a tab bar on top and the active TerminalSession below.
 * Replaces the old single TerminalPanel.
 */

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
      <div className="multi-terminal-tabs" role="tablist" aria-label="터미널 세션">
        <div className="terminal-tabs-scroll">
          {sessions.map(session => (
            <div
              key={session.id}
              className={`terminal-tab ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => setActiveSession(session.id)}
              title={`Terminal: ${session.name}`}
              role="tab"
              aria-selected={session.id === activeSessionId}
              aria-label={`터미널 세션: ${session.name}`}
            >
              <span className="terminal-tab-icon" aria-hidden="true">💻</span>
              <span className="terminal-tab-name">{session.name}</span>
              <button
                className="terminal-tab-close"
                onClick={e => { e.stopPropagation(); closeSession(session.id); }}
                title="Close terminal"
                aria-label={`${session.name} 터미널 닫기`}
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
          aria-label="새 터미널 세션 추가"
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
