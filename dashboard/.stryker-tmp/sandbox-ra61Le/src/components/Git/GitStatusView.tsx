/**
 * GitStatusView — File changes with staging/unstaging controls
 * ==============================================================
 * Shows staged and unstaged file changes ala VS Code source control.
 * Supports click-to-stage/unstage, file diff preview, and select all.
 */
// @ts-nocheck


import React, { useCallback } from 'react';
import { useGitStore, GitFile } from '../../stores/gitStore';

/* ─── Status Badge ────────────────────────────────────────── */

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    modified: '#fbbf24',
    added: '#10b981',
    deleted: '#ef4444',
    renamed: '#06b6d4',
    copied: '#a78bfa',
    untracked: '#6b7280',
    unknown: '#6b7280',
  };
  const labels: Record<string, string> = {
    modified: 'M',
    added: 'A',
    deleted: 'D',
    renamed: 'R',
    copied: 'C',
    untracked: '?',
    unknown: '?',
  };
  return (
    <span
      className="git-status-badge"
      style={{
        background: `${colors[status] || '#6b7280'}20`,
        color: colors[status] || '#6b7280',
        border: `1px solid ${colors[status] || '#6b7280'}40`,
      }}
      title={status}
    >
      {labels[status] || '?'}
    </span>
  );
}

/* ─── File Row ────────────────────────────────────────────── */

interface FileRowProps {
  file: GitFile;
  onStage: (file: string) => void;
  onUnstage: (file: string) => void;
  onShowDiff: (file: string) => void;
}

const FileRow: React.FC<FileRowProps> = React.memo(({ file, onStage, onUnstage, onShowDiff }) => {
  const isStaged = file.x !== ' ' && file.x !== '?';
  const isUnstaged = file.y !== ' ' && file.y !== '?';
  const isUntracked = file.x === '?' || file.y === '?';

  return (
    <div className="git-file-row" onClick={() => onShowDiff(file.file_path)} role="button" tabIndex={0}>
      <div className="git-file-statuses">
        {isStaged && <StatusBadge status={file.staged_status} />}
        {isUnstaged && <StatusBadge status={file.unstaged_status} />}
        {isUntracked && <StatusBadge status="untracked" />}
        {!isStaged && !isUnstaged && !isUntracked && <StatusBadge status="unknown" />}
      </div>
      <span className="git-file-path" title={file.file_path}>
        {file.is_renamed ? (
          <><span className="git-file-old">{file.old_path}</span> → <span>{file.file_path}</span></>
        ) : (
          file.file_path
        )}
      </span>
      <div className="git-file-actions">
        {isStaged ? (
          <button
            className="git-action-btn unstage"
            onClick={e => { e.stopPropagation(); onUnstage(file.file_path); }}
            title="Unstage"
          >
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
              <path d="M2 8h12M8 2v12" stroke="currentColor" strokeWidth="2" fill="none" />
            </svg>
          </button>
        ) : (
          <button
            className="git-action-btn stage"
            onClick={e => { e.stopPropagation(); onStage(file.file_path); }}
            title={isUntracked ? 'Stage' : 'Stage'}
          >
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
              <path d="M2 8h12M8 2v12" stroke="currentColor" strokeWidth="2" fill="none" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
});

FileRow.displayName = 'FileRow';

/* ─── GitStatusView ───────────────────────────────────────── */

const GitStatusView: React.FC = () => {
  const {
    status, fetchStatus, stageFiles, unstageFiles,
    fetchDiff, setShowStagedDiff, setCommitDialogOpen,
  } = useGitStore();
  const { branch, ahead, behind, files, counts, loading, error } = status;

  const handleRefresh = useCallback(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleStageAll = useCallback(() => {
    const unstagedFiles = files
      .filter(f => (f.y !== ' ' && f.y !== '?') || f.x === '?')
      .map(f => f.file_path);
    stageFiles(unstagedFiles);
  }, [files, stageFiles]);

  const handleUnstageAll = useCallback(() => {
    const stagedFiles = files
      .filter(f => f.x !== ' ' && f.x !== '?')
      .map(f => f.file_path);
    unstageFiles(stagedFiles);
  }, [files, unstageFiles]);

  const handleStage = useCallback((file: string) => {
    stageFiles([file]);
  }, [stageFiles]);

  const handleUnstage = useCallback((file: string) => {
    unstageFiles([file]);
  }, [unstageFiles]);

  const handleShowDiff = useCallback((file: string) => {
    fetchDiff(file, false);
    setShowStagedDiff(false);
  }, [fetchDiff, setShowStagedDiff]);

  const handleShowStagedDiff = useCallback(() => {
    fetchDiff('', true);
    setShowStagedDiff(true);
  }, [fetchDiff, setShowStagedDiff]);

  const handleOpenCommit = useCallback(() => {
    setCommitDialogOpen(true);
  }, [setCommitDialogOpen]);

  const stagedFiles = files.filter(f => f.x !== ' ' && f.x !== '?');
  const unstagedFiles = files.filter(f => f.y !== ' ' && f.y !== '?');
  const untrackedFiles = files.filter(f => f.x === '?' || f.y === '?');

  if (loading) {
    return <div className="git-loading"><span className="spinner spinner-sm" /> Loading status...</div>;
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
    <div className="git-status-view">
      {/* Header */}
      <div className="git-section-header">
        <div className="git-branch-info">
          <span className="git-branch-icon">📦</span>
          <span className="git-branch-name">{branch || 'main'}</span>
          {(ahead > 0 || behind > 0) && (
            <span className="git-branch-remote">
              {ahead > 0 && <span className="git-ahead">↑{ahead}</span>}
              {behind > 0 && <span className="git-behind">↓{behind}</span>}
            </span>
          )}
        </div>
        <div className="git-section-actions">
          {stagedFiles.length > 0 && <button className="git-action-btn-sm" onClick={handleUnstageAll} title="Unstage All">↩</button>}
          {unstagedFiles.length > 0 && <button className="git-action-btn-sm" onClick={handleStageAll} title="Stage All">↪</button>}
          <button className="git-action-btn-sm" onClick={handleRefresh} title="Refresh">🔄</button>
        </div>
      </div>

      {/* Summary */}
      <div className="git-summary">
        <span className="git-summary-item">
          <span className="git-dot staged" /> {counts.staged} staged
        </span>
        <span className="git-summary-item">
          <span className="git-dot unstaged" /> {counts.unstaged} unstaged
        </span>
        <span className="git-summary-item">
          <span className="git-dot untracked" /> {counts.untracked} untracked
        </span>
      </div>

      {/* Staged files */}
      {stagedFiles.length > 0 && (
        <div className="git-file-section">
          <div className="git-file-section-header" onClick={handleShowStagedDiff}>
            <span>Staged Changes</span>
            <span className="git-file-count">{stagedFiles.length}</span>
          </div>
          {stagedFiles.map(f => (
            <FileRow key={f.file_path} file={f} onStage={handleStage} onUnstage={handleUnstage} onShowDiff={handleShowDiff} />
          ))}
        </div>
      )}

      {/* Unstaged files */}
      {unstagedFiles.length > 0 && (
        <div className="git-file-section">
          <div className="git-file-section-header">
            <span>Changes</span>
            <span className="git-file-count">{unstagedFiles.length}</span>
          </div>
          {unstagedFiles.map(f => (
            <FileRow key={f.file_path} file={f} onStage={handleStage} onUnstage={handleUnstage} onShowDiff={handleShowDiff} />
          ))}
        </div>
      )}

      {/* Untracked files */}
      {untrackedFiles.length > 0 && (
        <div className="git-file-section">
          <div className="git-file-section-header">
            <span>Untracked</span>
            <span className="git-file-count">{untrackedFiles.length}</span>
          </div>
          {untrackedFiles.map(f => (
            <FileRow key={f.file_path} file={f} onStage={handleStage} onUnstage={handleUnstage} onShowDiff={handleShowDiff} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {files.length === 0 && (
        <div className="git-empty">
          <span className="git-empty-icon">✅</span>
          <span>No changes — working tree is clean</span>
        </div>
      )}

      {/* Commit Button */}
      {files.length > 0 && (
        <div className="git-commit-bar">
          <button className="glow-btn" onClick={handleOpenCommit} style={{ width: '100%', padding: '8px 0', fontSize: 12 }}>
            💾 Commit ({counts.total} file{counts.total !== 1 ? 's' : ''})
          </button>
        </div>
      )}
    </div>
  );
};

export default GitStatusView;
