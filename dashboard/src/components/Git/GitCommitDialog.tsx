/**
 * GitCommitDialog — Modal for creating a commit
 * ===============================================
 * Provides commit message input, optional stage all toggle,
 * and shows files to be committed.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useGitStore } from '../../stores/gitStore';
import { useUiStore } from '../../stores/uiStore';

/* ─── Git Commit Dialog ───────────────────────────────────── */

const GitCommitDialog: React.FC = () => {
  const {
    commitDialogOpen, commitMessage, commitStageAll,
    setCommitDialogOpen, setCommitMessage, setCommitStageAll,
    commit, status, fetchStatus,
  } = useGitStore();
  const { addToast } = useUiStore();
  const [committing, setCommitting] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Focus input when dialog opens
  useEffect(() => {
    if (commitDialogOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [commitDialogOpen]);

  const handleClose = useCallback(() => {
    if (committing) return;
    setCommitDialogOpen(false);
  }, [committing, setCommitDialogOpen]);

  const handleCommit = useCallback(async () => {
    if (!commitMessage.trim()) return;
    setCommitting(true);
    const ok = await commit(commitMessage, commitStageAll);
    setCommitting(false);
    if (ok) {
      addToast('✅ Commit created successfully!', 'success');
      setCommitDialogOpen(false);
      setCommitMessage('');
      fetchStatus();
    } else {
      addToast('❌ Commit failed', 'error');
    }
  }, [commitMessage, commitStageAll, commit, fetchStatus, setCommitDialogOpen, setCommitMessage, addToast]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleCommit();
    }
    if (e.key === 'Escape' && !committing) {
      handleClose();
    }
  }, [handleCommit, handleClose, committing]);

  const stagedFiles = status.files.filter(f => f.x !== ' ' && f.x !== '?');
  const unstagedFiles = status.files.filter(f => f.y !== ' ' && f.y !== '?');

  const canCommit = commitMessage.trim().length > 0 && !committing;

  if (!commitDialogOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div
        className="modal-content glass-panel git-commit-dialog"
        onClick={e => e.stopPropagation()}
        style={{ width: 520, maxHeight: '70vh' }}
      >
        {/* Header */}
        <div className="git-commit-header">
          <h3>💾 Commit Changes</h3>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            <span className="git-branch-name">{status.branch || 'main'}</span>
          </div>
          <button className="icon-btn" onClick={handleClose} disabled={committing} style={{ fontSize: 12, padding: '4px 8px', color: 'var(--text-secondary)' }}>✕</button>
        </div>

        {/* Branch info */}
        <div className="git-commit-info">
          <span className="git-commit-branch">📦 {status.branch || 'main'}</span>
          <span className="git-commit-counts">
            {status.counts.total} file{status.counts.total !== 1 ? 's' : ''} to commit
          </span>
        </div>

        {/* Commit message */}
        <div className="git-commit-body">
          <textarea
            ref={inputRef}
            className="git-commit-input"
            value={commitMessage}
            onChange={e => setCommitMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Commit message (Ctrl+Enter to commit)"
            rows={3}
            disabled={committing}
          />

          {/* Stage all toggle */}
          <label className="toggle-switch" style={{ marginTop: 8 }}>
            <input
              type="checkbox"
              checked={commitStageAll}
              onChange={e => setCommitStageAll(e.target.checked)}
              disabled={committing}
            />
            <span className="toggle-track" />
            <span className="toggle-label">
              Stage all changes before commit
              <small>Automatically stage all modified/untracked files</small>
            </span>
          </label>

          {/* Files to commit */}
          {stagedFiles.length > 0 && (
            <div className="git-commit-files" style={{ marginTop: 12 }}>
              <div className="git-commit-files-header">
                <span>Staged Files ({stagedFiles.length})</span>
              </div>
              {stagedFiles.map(f => (
                <div key={f.file_path} className="git-commit-file">
                  <span className={`git-file-status-dot ${f.staged_status}`} />
                  {f.file_path}
                </div>
              ))}
            </div>
          )}

          {commitStageAll && unstagedFiles.length > 0 && (
            <div className="git-commit-files" style={{ marginTop: 8 }}>
              <div className="git-commit-files-header" style={{ color: 'var(--text-muted)' }}>
                <span>Will also stage ({unstagedFiles.length} unstaged)</span>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="git-commit-actions">
          <button
            className="glass-btn small"
            onClick={handleClose}
            disabled={committing}
          >
            Cancel
          </button>
          <button
            className="glow-btn"
            onClick={handleCommit}
            disabled={!canCommit}
            style={{ fontSize: 12, padding: '6px 16px' }}
          >
            {committing ? (
              <><span className="spinner spinner-sm" /> Committing...</>
            ) : (
              <>💾 Commit on {status.branch || 'main'}</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default GitCommitDialog;
