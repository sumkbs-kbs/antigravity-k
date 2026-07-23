/**
 * StatusBar — VS Code-style status bar
 * ======================================
 * Displays at the bottom of the editor area with:
 * - Error/warning counts (links to Problems panel)
 * - Cursor position (line:column)
 * - Active file encoding/language
 * - Indentation info
 * - Save indicator
 */
// @ts-nocheck


import React, { useCallback, useState, useEffect } from 'react';
import { useEditorStore } from '../../stores/editorStore';
import { useProblemsStore } from '../../stores/problemsStore';

const StatusBar: React.FC = () => {
  const openFiles = useEditorStore(s => s.openFiles);
  const activeFilePath = useEditorStore(s => s.activeFilePath);
  const errorCount = useProblemsStore(s => s.errorCount);
  const warningCount = useProblemsStore(s => s.warningCount);
  const setProblemsPanelVisible = useProblemsStore(s => s.setProblemsPanelVisible);
  const problemsPanelVisible = useProblemsStore(s => s.problemsPanelVisible);

  const activeFile = openFiles.find(f => f.path === activeFilePath);
  const [cursorPosition, setCursorPosition] = useState({ line: 1, column: 1 });

  const errCount = errorCount();
  const warnCount = warningCount();
  const hasProblems = errCount + warnCount > 0;

  // Listen for cursor position changes from Monaco
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      const { line, column } = e.detail || {};
      if (line !== undefined && column !== undefined) {
        setCursorPosition({ line, column });
      }
    };
    window.addEventListener('agk:cursor-position', handler as EventListener);
    return () => window.removeEventListener('agk:cursor-position', handler as EventListener);
  }, []);

  // Reset cursor when file changes
  useEffect(() => {
    setCursorPosition({ line: 1, column: 1 });
  }, [activeFilePath]);

  const handleProblemsClick = useCallback(() => {
    setProblemsPanelVisible(!problemsPanelVisible);
  }, [problemsPanelVisible, setProblemsPanelVisible]);

  const indentKind = activeFile?.language === 'python' ? 'Spaces: 4' : 'Spaces: 2';

  return (
    <div className="status-bar">
      {/* Left side */}
      <div className="status-bar-left">
        {/* Problems count */}
        <button
          className={`status-bar-item status-problems ${hasProblems ? 'has-issues' : ''}`}
          onClick={handleProblemsClick}
          title={hasProblems ? `${errCount} errors, ${warnCount} warnings` : 'No problems'}
        >
          {hasProblems ? (
            <>
              {errCount > 0 && <span className="status-item-err">✕ {errCount}</span>}
              {warnCount > 0 && <span className="status-item-warn">⚠ {warnCount}</span>}
              {errCount === 0 && warnCount === 0 && <span className="status-item-ok">✓</span>}
            </>
          ) : (
            <span className="status-item-ok">✓ No problems</span>
          )}
        </button>

        {/* File encoding */}
        {activeFile && (
          <>
            <div className="status-bar-separator" />
            <span className="status-bar-item" title="File encoding">
              UTF-8
            </span>
          </>
        )}
      </div>

      {/* Right side */}
      <div className="status-bar-right">
        {activeFile && (
          <>
            {/* Indentation */}
            <span className="status-bar-item" title="Indentation">
              {indentKind}
            </span>
            <div className="status-bar-separator" />

            {/* Language */}
            <span className="status-bar-item" title="Programming Language">
              <span className="status-bar-lang-dot" style={{
                background: getLangColor(activeFile.language),
              }} />
              {activeFile.language}
            </span>
            <div className="status-bar-separator" />

            {/* Cursor position */}
            <span className="status-bar-item" title="Line and Column">
              Ln {cursorPosition.line}, Col {cursorPosition.column}
            </span>
          </>
        )}

        {/* File type icon */}
        <div className="status-bar-separator" />
        <span className="status-bar-item" title="File type">
          {activeFile?.isDirty ? (
            <span style={{ color: '#ff9e64' }}>◉ Modified</span>
          ) : (
            <span style={{ color: 'var(--text-muted)' }}>○</span>
          )}
        </span>
      </div>
    </div>
  );
};

/* ─── Language Color Map ──────────────────────────────────── */

function getLangColor(lang: string): string {
  const colors: Record<string, string> = {
    typescript: '#3178c6',
    javascript: '#f7df1e',
    python: '#3572a5',
    rust: '#dea584',
    go: '#00add8',
    java: '#b07219',
    cpp: '#f34b7d',
    c: '#555555',
    css: '#563d7c',
    html: '#e34f26',
    json: '#292929',
    markdown: '#083fa1',
    shell: '#89e051',
    sql: '#e38c00',
    yaml: '#cb171e',
  };
  return colors[lang] || 'var(--text-muted)';
}

export default StatusBar;
