/**
 * GitPanel — Main Git panel with tab-based views
 * ================================================
 * Tab navigation between Status, Log, Branches, and Diff views.
 * Integrates GitCommitDialog for commit workflow.
 */

import React, { useEffect, useCallback } from 'react';
import { useGitStore } from '../../stores/gitStore';
import GitStatusView from './GitStatusView';
import GitLogView from './GitLogView';
import GitDiffView from './GitDiffView';
import GitCommitDialog from './GitCommitDialog';

const GIT_TABS = [
  { id: 'status' as const, label: 'Changes', icon: '📝' },
  { id: 'log' as const, label: 'History', icon: '📜' },
  { id: 'branches' as const, label: 'Branches', icon: '🌿' },
  { id: 'graph' as const, label: 'Graph', icon: '🔀' },
];

/* ─── Branches View ───────────────────────────────────────── */

const BranchesView: React.FC = () => {
  const { branches, fetchBranches, checkoutBranch, createBranch, deleteBranch } = useGitStore();
  const { list, current, loading, error } = branches;

  const handleRefresh = useCallback(() => fetchBranches(), [fetchBranches]);

  useEffect(() => {
    if (list.length === 0) fetchBranches();
  }, [fetchBranches, list.length]);

  const handleCheckout = useCallback((name: string) => {
    if (name === current) return;
    if (confirm(`Switch to branch "${name}"?`)) {
      checkoutBranch(name);
    }
  }, [current, checkoutBranch]);

  const handleDelete = useCallback((name: string) => {
    if (name === current) return;
    if (confirm(`Delete branch "${name}"?`)) {
      deleteBranch(name);
    }
  }, [current, deleteBranch]);

  const handleCreateNew = useCallback(() => {
    const name = prompt('New branch name:');
    if (name?.trim()) {
      createBranch(name.trim());
    }
  }, [createBranch]);

  if (loading) {
    return <div className="git-loading"><span className="spinner spinner-sm" /> Loading branches...</div>;
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
    <div className="git-branches-view">
      <div className="git-section-header">
        <span className="git-section-title">🌿 Branches</span>
        <div className="git-section-actions">
          <button className="git-action-btn-sm" onClick={handleCreateNew} title="Create New Branch">➕</button>
          <button className="git-action-btn-sm" onClick={handleRefresh} title="Refresh">🔄</button>
        </div>
      </div>

      {list.length === 0 ? (
        <div className="git-empty"><span>No branches found</span></div>
      ) : (
        <div className="git-branches-list">
          {/* Local branches */}
          {list.filter(b => !b.is_remote).map(b => (
            <div
              key={b.name}
              className={`git-branch-row ${b.is_current ? 'current' : ''}`}
              onClick={() => handleCheckout(b.name)}
              role="button"
              tabIndex={0}
            >
              <span className="git-branch-indicator">
                {b.is_current ? <span className="git-current-dot" /> : '  '}
              </span>
              <span className="git-branch-row-name">{b.name}</span>
              {b.upstream && <span className="git-branch-upstream">{b.upstream}</span>}
              {!b.is_current && (
                <button
                  className="git-action-btn-sm danger"
                  onClick={e => { e.stopPropagation(); handleDelete(b.name); }}
                  title="Delete branch"
                >
                  🗑️
                </button>
              )}
            </div>
          ))}

          {/* Remote branches */}
          {list.filter(b => b.is_remote).length > 0 && (
            <>
              <div className="git-branches-divider">Remote</div>
              {list.filter(b => b.is_remote).map(b => (
                <div
                  key={b.name}
                  className="git-branch-row remote"
                  onClick={() => handleCheckout(b.name)}
                  role="button"
                  tabIndex={0}
                >
                  <span className="git-branch-indicator"> </span>
                  <span className="git-branch-row-name">{b.name.replace('remotes/', '')}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};

/* ─── Graph View ──────────────────────────────────────────── */

const GraphView: React.FC = () => {
  const { graph, fetchGraph } = useGitStore();
  const { nodes, loading, error } = graph;

  useEffect(() => {
    if (nodes.length === 0) fetchGraph();
  }, [fetchGraph, nodes.length]);

  const handleRefresh = useCallback(() => fetchGraph(), [fetchGraph]);

  if (loading) {
    return <div className="git-loading"><span className="spinner spinner-sm" /> Loading graph...</div>;
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
    <div className="git-graph-view">
      <div className="git-section-header">
        <span className="git-section-title">🔀 Branch Graph</span>
        <div className="git-section-actions">
          <span className="git-count-badge">{nodes.length} commits</span>
          <button className="git-action-btn-sm" onClick={handleRefresh}>🔄</button>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div className="git-empty"><span>No commits in graph</span></div>
      ) : (
        <div className="git-graph-list">
          {nodes.map((node, i) => {
            // Convert graph characters to colored spans
            const graphHtml = node.graph.replace(/\*/g, '●').replace(/[|/\\_\-.]/g, c => c);
            const date = node.date ? new Date(node.date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }) : '';
            return (
              <div key={i} className="git-graph-row">
                <span className="git-graph-visual" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'pre' }}>
                  {graphHtml}
                </span>
                <span className="git-graph-dot">●</span>
                <span className="git-graph-message">{node.message}</span>
                <span className="git-graph-meta">
                  <span className="git-graph-hash">{node.short_hash}</span>
                  <span className="git-graph-date">{date}</span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ─── GitPanel ────────────────────────────────────────────── */

const GitPanel: React.FC = () => {
  const { activeTab, setActiveTab, fetchStatus, fetchLog, fetchBranches, fetchGraph } = useGitStore();

  // Load initial data
  useEffect(() => {
    fetchStatus();
    fetchLog();
    fetchBranches();
    fetchGraph();
  }, [fetchStatus, fetchLog, fetchBranches, fetchGraph]);

  return (
    <div className="git-panel glass-panel">
      {/* Tabs */}
      <div className="git-tabs">
        {GIT_TABS.map(tab => (
          <button
            key={tab.id}
            className={`git-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="git-tab-icon">{tab.icon}</span>
            <span className="git-tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="git-tab-content">
        {activeTab === 'status' && <GitStatusView />}
        {activeTab === 'log' && <GitLogView />}
        {activeTab === 'branches' && <BranchesView />}
        {activeTab === 'graph' && <GraphView />}
      </div>

      {/* Diff Panel (bottom, when showing diff) */}
      <GitDiffView />

      {/* Commit Dialog */}
      <GitCommitDialog />
    </div>
  );
};

export default GitPanel;
