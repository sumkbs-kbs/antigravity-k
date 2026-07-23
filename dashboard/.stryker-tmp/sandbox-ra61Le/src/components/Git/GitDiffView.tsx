/**
 * GitDiffView — Inline git diff display with syntax coloring
 * ============================================================
 * Parses unified diff output and renders with line-by-line
 * color highlighting (green for additions, red for deletions).
 */
// @ts-nocheck


import React from 'react';
import { useGitStore } from '../../stores/gitStore';
import { parseDiff, type DiffLine } from '../../utils/diffParser';

/* ─── DiffLineComponent ───────────────────────────────────── */

const DiffLineComponent: React.FC<{ line: DiffLine; index: number }> = React.memo(({ line, index }) => {
  const className = `git-diff-line git-diff-${line.type}`;
  const prefix = line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ';

  return (
    <div className={className} key={index}>
      <span className="git-diff-line-no">{index + 1}</span>
      <span className="git-diff-prefix">{prefix}</span>
      <span className="git-diff-text">{line.content}</span>
    </div>
  );
});
DiffLineComponent.displayName = 'DiffLineComponent';

/* ─── GitDiffView ─────────────────────────────────────────── */

const GitDiffView: React.FC = () => {
  const { diff, showStagedDiff, fetchDiff, setShowStagedDiff } = useGitStore();
  const { content, stat, loading, error } = diff;

  const parsedLines = content ? parseDiff(content) : [];

  if (loading) {
    return <div className="git-loading"><span className="spinner spinner-sm" /> Loading diff...</div>;
  }

  if (error) {
    return <div className="git-error">⚠️ {error}</div>;
  }

  if (!content) {
    return (
      <div className="git-diff-view">
        <div className="git-section-header">
          <span className="git-section-title">📋 Diff</span>
          <div className="git-section-actions">
            <button
              className={`git-action-btn-sm ${showStagedDiff ? 'active' : ''}`}
              onClick={() => { fetchDiff('', !showStagedDiff); setShowStagedDiff(!showStagedDiff); }}
              title="Toggle staged/unstaged"
            >
              {showStagedDiff ? 'Staged' : 'Unstaged'}
            </button>
          </div>
        </div>
        <div className="git-empty">
          <span>Select a file or commit to view its diff</span>
        </div>
      </div>
    );
  }

  // Parse stat lines
  const statLines = stat.split('\n').filter(Boolean);

  return (
    <div className="git-diff-view">
      <div className="git-section-header">
        <span className="git-section-title">
          📋 {showStagedDiff ? 'Staged' : 'Unstaged'} Diff
        </span>
        <div className="git-section-actions">
          <button
            className={`git-action-btn-sm ${showStagedDiff ? '' : 'active'}`}
            onClick={() => { fetchDiff('', !showStagedDiff); setShowStagedDiff(!showStagedDiff); }}
            title="Toggle staged/unstaged"
          >
            {showStagedDiff ? 'Show Unstaged' : 'Show Staged'}
          </button>
        </div>
      </div>

      {/* Stat summary */}
      {statLines.length > 0 && (
        <div className="git-diff-stat">
          {statLines.map((line, i) => (
            <div key={i} className="git-diff-stat-line">{line}</div>
          ))}
        </div>
      )}

      {/* Diff content */}
      <div className="git-diff-content">
        {parsedLines.length === 0 ? (
          <div className="git-empty">No changes in diff</div>
        ) : (
          parsedLines.map((line, i) => <DiffLineComponent key={i} line={line} index={i} />)
        )}
      </div>
    </div>
  );
};

export default GitDiffView;
