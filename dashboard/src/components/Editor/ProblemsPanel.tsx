/**
 * ProblemsPanel — VS Code-style Problems panel
 * ===============================================
 * Displays diagnostics (errors, warnings, info) from Monaco's built-in
 * TypeScript/JavaScript language service. Shows file path, line, column,
 * message, and severity with clickable items to navigate to the source.
 * Supports filtering by severity and text search.
 */

import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import { useProblemsStore, getFilteredProblems, ProblemSeverity, Problem } from '../../stores/problemsStore';
import { useEditorStore } from '../../stores/editorStore';
import { useUiStore } from '../../stores/uiStore';

/* ─── Severity Icon ────────────────────────────────────────── */

function SeverityIcon({ severity }: { severity: ProblemSeverity }) {
  switch (severity) {
    case 'error':
      return (
        <svg width="14" height="14" viewBox="0 0 16 16" fill="#ef4444" style={{ flexShrink: 0 }}>
          <circle cx="8" cy="8" r="7" fill="#ef4444" opacity="0.2" />
          <path d="M4 4l8 8M12 4l-8 8" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case 'warning':
      return (
        <svg width="14" height="14" viewBox="0 0 16 16" fill="#fbbf24" style={{ flexShrink: 0 }}>
          <circle cx="8" cy="8" r="7" fill="#fbbf24" opacity="0.2" />
          <path d="M8 4.5v4M8 11v.5" stroke="#fbbf24" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case 'info':
      return (
        <svg width="14" height="14" viewBox="0 0 16 16" fill="#06b6d4" style={{ flexShrink: 0 }}>
          <circle cx="8" cy="8" r="7" fill="#06b6d4" opacity="0.2" />
          <circle cx="8" cy="5.5" r="1" fill="#06b6d4" />
          <path d="M7.5 8h1v4h-1z" fill="#06b6d4" />
        </svg>
      );
  }
}

/* ─── Problem Row ──────────────────────────────────────────── */

interface ProblemRowProps {
  problem: Problem;
  onClick: (problem: Problem) => void;
}

const ProblemRow: React.FC<ProblemRowProps> = React.memo(({ problem, onClick }) => {
  const handleClick = useCallback(() => onClick(problem), [problem, onClick]);

  return (
    <div
      className="problems-row"
      onClick={handleClick}
      title={`${problem.filePath}:${problem.line}:${problem.column} — ${problem.message}`}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') handleClick(); }}
    >
      <SeverityIcon severity={problem.severity} />
      <span className="problems-message">{problem.message}</span>
      {problem.code && (
        <span className="problems-code">{problem.code}</span>
      )}
      <span className="problems-location">
        {problem.fileName}:{problem.line}:{problem.column}
      </span>
    </div>
  );
});

ProblemRow.displayName = 'ProblemRow';

/* ─── Problems Panel ───────────────────────────────────────── */

const ProblemsPanel: React.FC = () => {
  const {
    problems, activeFilePath, filterSeverity, filterText, problemsPanelVisible,
    setFilterSeverity, setFilterText, setProblemsPanelVisible,
    errorCount, warningCount, infoCount,
  } = useProblemsStore();
  const { openFile } = useEditorStore();
  const { addToast } = useUiStore();
  const filterInputRef = useRef<HTMLInputElement>(null);

  const filteredProblems = useMemo(
    () => getFilteredProblems(problems, activeFilePath, filterSeverity, filterText),
    [problems, activeFilePath, filterSeverity, filterText],
  );

  // Group by file
  const groupedByFile = useMemo(() => {
    const groups: Record<string, Problem[]> = {};
    for (const p of filteredProblems) {
      if (!groups[p.filePath]) groups[p.filePath] = [];
      groups[p.filePath].push(p);
    }
    return groups;
  }, [filteredProblems]);

  // Focus filter input when panel opens
  useEffect(() => {
    if (problemsPanelVisible && filterInputRef.current) {
      setTimeout(() => filterInputRef.current?.focus(), 50);
    }
  }, [problemsPanelVisible]);

  const handleProblemClick = useCallback(async (problem: Problem) => {
    try {
      const res = await fetch(`/api/fs/read?file=${encodeURIComponent(problem.filePath)}`);
      const data = await res.json();
      if (data.content !== undefined) {
        openFile(problem.filePath, problem.fileName, data.content);
        // Dispatch event to navigate to line
        window.dispatchEvent(new CustomEvent('agk:editor-reveal-line', {
          detail: { line: problem.line, column: problem.column },
        }));
      }
    } catch (err: any) {
      addToast(`파일 열기 오류: ${err.message}`, 'error');
    }
  }, [openFile, addToast]);

  const handleTogglePanel = useCallback(() => {
    setProblemsPanelVisible(!problemsPanelVisible);
  }, [problemsPanelVisible, setProblemsPanelVisible]);

  const errCount = errorCount();
  const warnCount = warningCount();
  const infCount = infoCount();
  const hasProblems = errCount + warnCount + infCount > 0;

  return (
    <>
      {/* Problems Panel Content */}
      <div
        className={`problems-panel ${problemsPanelVisible ? 'visible' : ''}`}
        style={{
          display: problemsPanelVisible ? 'flex' : 'none',
          flexDirection: 'column',
          overflow: 'hidden',
          background: '#1a1b2e',
          borderTop: '1px solid var(--glass-border)',
          height: 180,
          minHeight: 100,
          flexShrink: 0,
        }}
      >
        {/* Header */}
        <div className="problems-header">
          <div className="problems-header-left">
            <span className="problems-title">PROBLEMS</span>
            {hasProblems && (
              <span className="problems-counts">
                {errCount > 0 && <span className="problems-count errors">{errCount} error{errCount !== 1 ? 's' : ''}</span>}
                {warnCount > 0 && <span className="problems-count warnings">{warnCount} warning{warnCount !== 1 ? 's' : ''}</span>}
                {infCount > 0 && <span className="problems-count infos">{infCount} info{infCount !== 1 ? 's' : ''}</span>}
              </span>
            )}
          </div>
          <div className="problems-header-right">
            {/* Severity filter chips */}
            <div className="problems-filter-chips">
              {(['all', 'error', 'warning', 'info'] as const).map(s => (
                <button
                  key={s}
                  className={`problems-chip ${filterSeverity === s ? 'active' : ''}`}
                  onClick={() => setFilterSeverity(s)}
                >
                  {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            {/* Text filter */}
            <input
              ref={filterInputRef}
              type="text"
              className="problems-filter-input"
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              placeholder="Filter..."
              onKeyDown={e => e.key === 'Escape' && setFilterText('')}
            />
            {/* Close button */}
            <button
              className="icon-btn"
              onClick={handleTogglePanel}
              title="Close Problems Panel"
              style={{ fontSize: 11, padding: '3px 6px', color: 'var(--text-muted)' }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="problems-body">
          {Object.keys(groupedByFile).length === 0 ? (
            <div className="problems-empty">
              {filterText || filterSeverity !== 'all'
                ? <span>No problems matching filter</span>
                : <span>✨ No problems detected in active file</span>
              }
            </div>
          ) : (
            Object.entries(groupedByFile).map(([filePath, fileProblems]) => (
              <div key={filePath} className="problems-file-group">
                <div className="problems-file-header">
                  <span className="problems-file-icon">📄</span>
                  <span className="problems-file-path">{filePath}</span>
                  <span className="problems-file-count">{fileProblems.length}</span>
                </div>
                {fileProblems.map(p => (
                  <ProblemRow key={p.id} problem={p} onClick={handleProblemClick} />
                ))}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Problems count button (shown in status bar) */}
      <button
        className={`problems-toggle-btn ${problemsPanelVisible ? 'active' : ''}`}
        onClick={handleTogglePanel}
        title={problemsPanelVisible ? 'Close Problems' : 'Open Problems'}
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ flexShrink: 0 }}>
          <path d="M2 2h12v1H2zM2 5h12v1H2zM2 8h12v1H2zM2 11h8v1H2z" />
        </svg>
        {hasProblems && (
          <>
            {errCount > 0 && <span className="status-err">{errCount}</span>}
            {warnCount > 0 && <span className="status-warn">{warnCount}</span>}
          </>
        )}
      </button>
    </>
  );
};

export default ProblemsPanel;
