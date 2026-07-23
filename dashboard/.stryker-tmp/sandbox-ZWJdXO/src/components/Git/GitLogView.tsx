/**
 * GitLogView — Commit history with clickable commits
 * ====================================================
 * Shows recent commits with author, date, message.
 * Click a commit to view its diff in the diff panel.
 */
// @ts-nocheck


import React, { useCallback } from 'react';
import { useGitStore, GitCommit } from '../../stores/gitStore';

/* ─── Commit Row ──────────────────────────────────────────── */

interface CommitRowProps {
  commit: GitCommit;
  isSelected: boolean;
  onSelect: (commit: GitCommit) => void;
}

const CommitRow: React.FC<CommitRowProps> = React.memo(({ commit, isSelected, onSelect }) => {
  const handleClick = useCallback(() => onSelect(commit), [commit, onSelect]);

  const date = new Date(commit.date);
  const dateStr = date.toLocaleDateString('ko-KR', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  // Extract branch refs
  const refs = commit.refs ? commit.refs.split(',').map(r => r.trim()).filter(Boolean) : [];

  return (
    <div
      className={`git-log-row ${isSelected ? 'selected' : ''}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && handleClick()}
    >
      <div className="git-log-dot" />
      <div className="git-log-content">
        <div className="git-log-message">{commit.message}</div>
        <div className="git-log-meta">
          <span className="git-log-hash">{commit.short_hash}</span>
          <span className="git-log-author">{commit.author_name}</span>
          <span className="git-log-date">{dateStr}</span>
        </div>
        {refs.length > 0 && (
          <div className="git-log-refs">
            {refs.filter(r => !r.startsWith('HEAD')).map((ref, i) => (
              <span key={i} className={`git-ref-badge ${ref.startsWith('tag:') ? 'tag' : 'branch'}`}>
                {ref.replace('tag: ', '').replace('origin/', '')}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
});
CommitRow.displayName = 'CommitRow';

/* ─── GitLogView ──────────────────────────────────────────── */

const GitLogView: React.FC = () => {
  const { log, fetchLog, setSelectedLogCommit, selectedLogCommit, fetchDiff } = useGitStore();
  const { commits, loading, error } = log;

  const handleRefresh = useCallback(() => {
    fetchLog();
  }, [fetchLog]);

  const handleSelect = useCallback((commit: GitCommit) => {
    setSelectedLogCommit(commit);
    fetchDiff('', false, '.');
  }, [setSelectedLogCommit, fetchDiff]);

  if (loading) {
    return <div className="git-loading"><span className="spinner spinner-sm" /> Loading history...</div>;
  }

  if (error) {
    return (
      <div className="git-error">
        <div>⚠️ {error}</div>
        <button className="glass-btn small" onClick={handleRefresh}>Retry</button>
      </div>
    );
  }

  return (
    <div className="git-log-view">
      <div className="git-section-header">
        <span className="git-section-title">📜 Commit History</span>
        <div className="git-section-actions">
          <span className="git-count-badge">{commits.length} commits</span>
          <button className="git-action-btn-sm" onClick={handleRefresh} title="Refresh">🔄</button>
        </div>
      </div>

      {commits.length === 0 ? (
        <div className="git-empty">
          <span>No commits yet</span>
        </div>
      ) : (
        <div className="git-log-list">
          {commits.map(c => (
            <CommitRow
              key={c.hash}
              commit={c}
              isSelected={selectedLogCommit?.hash === c.hash}
              onSelect={handleSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default GitLogView;
