/**
 * ChangePanel — Review proposed file changes with diff view
 * ==========================================================
 * Lists all proposed file changes from AI interactions.
 * Shows diff preview, accept/reject buttons, and bulk actions.
 * Integrates with the IDE layout as a collapsible side panel.
 */
// @ts-nocheck


import React, { useCallback, useRef, useEffect } from 'react';
import { useChangeStore, ProposedChange } from '../../stores/changeStore';
import { useUiStore } from '../../stores/uiStore';
import DiffViewer from './DiffViewer';
import { useFileStore } from '../../stores/fileStore';

/* ─── Change Card (compact list view) ─────────────────────── */

interface ChangeCardProps {
  change: ProposedChange;
  isSelected: boolean;
  onClick: (id: string) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

const ChangeCard: React.FC<ChangeCardProps> = ({
  change,
  isSelected,
  onClick,
  onApprove,
  onReject,
}) => {
  const statusIcon: Record<string, string> = {
    pending: '⏳',
    approved: '✅',
    rejected: '❌',
    applied: '✔️',
    failed: '⚠️',
  };

  const handleClick = useCallback(() => onClick(change.id), [change.id, onClick]);

  const handleApprove = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onApprove(change.id);
    },
    [change.id, onApprove],
  );

  const handleReject = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onReject(change.id);
    },
    [change.id, onReject],
  );

  const fileName = change.fileName || change.filePath.split('/').pop() || change.filePath;
  const dirPath = change.filePath.split('/').slice(0, -1).join('/');

  return (
    <div
      className={`change-card ${change.status} ${isSelected ? 'selected' : ''}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
    >
      <div className="change-card-header">
        <span className="change-file-icon">📄</span>
        <div className="change-file-info">
          <span className="change-file-name">{fileName}</span>
          {dirPath && <span className="change-file-dir">{dirPath}</span>}
        </div>
        <span className="change-status-icon" title={change.status}>
          {statusIcon[change.status] || '⏳'}
        </span>
      </div>

      {change.diffStats && (
        <div className="change-stats-row">
          <span className="change-stat-added">+{change.diffStats.additions}</span>
          <span className="change-stat-removed">-{change.diffStats.deletions}</span>
          {change.description && (
            <span className="change-desc-text">{change.description}</span>
          )}
        </div>
      )}

      {change.status === 'pending' && (
        <div className="change-card-actions">
          <button
            className="change-action-btn reject"
            onClick={handleReject}
            title="거절"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            거절
          </button>
          <button
            className="change-action-btn approve"
            onClick={handleApprove}
            title="승인"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            승인
          </button>
        </div>
      )}
    </div>
  );
};

/* ─── ChangePanel Component ────────────────────────────────── */

interface ChangePanelProps {
  visible?: boolean;
  onClose?: () => void;
}

const ChangePanel: React.FC<ChangePanelProps> = ({ visible, onClose }) => {
  const {
    changes,
    selectedChangeId,
    panelMode,
    pendingCount,
    selectChange,
    approveChange,
    rejectChange,
    approveAll,
    rejectAll,
    setPanelMode,
    clearChanges,
  } = useChangeStore();
  const { addToast } = useUiStore();
  const panelRef = useRef<HTMLDivElement>(null);
  const { refreshTree } = useFileStore();

  const selectedChange = changes.find((c) => c.id === selectedChangeId) || null;
  const pendingChanges = changes.filter((c) => c.status === 'pending');
  const hasPending = pendingChanges.length > 0;
  const hasChanges = changes.length > 0;

  // Escape key to close
  useEffect(() => {
    if (!visible) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (panelMode === 'diff') {
          setPanelMode('list');
        } else {
          onClose?.();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [visible, panelMode, setPanelMode, onClose]);

  const handleApproveChange = useCallback(
    (id: string) => {
      approveChange(id);
      addToast('✅ 변경 승인됨', 'success');
    },
    [approveChange, addToast],
  );

  const handleRejectChange = useCallback(
    (id: string) => {
      rejectChange(id);
      addToast('❌ 변경 거절됨', 'error');
    },
    [rejectChange, addToast],
  );

  const handleApproveAll = useCallback(async () => {
    approveAll();
    addToast(`✅ ${pendingChanges.length}개 변경 일괄 승인됨`, 'success');
    // Trigger file refresh if any changes were approved
    await refreshTree();
  }, [approveAll, pendingChanges.length, addToast, refreshTree]);

  const handleRejectAll = useCallback(() => {
    rejectAll();
    addToast(`❌ ${pendingChanges.length}개 변경 일괄 거절됨`, 'error');
  }, [rejectAll, pendingChanges.length, addToast]);

  const handleClear = useCallback(() => {
    if (changes.length === 0) return;
    clearChanges();
    addToast('🗑️ 변경 목록 초기화됨', 'info');
  }, [changes.length, clearChanges, addToast]);

  const handleBack = useCallback(() => {
    setPanelMode('list');
    selectChange(null);
  }, [setPanelMode, selectChange]);

  if (!visible) return null;

  return (
    <div className="change-panel glass-panel" ref={panelRef}>
      {/* Panel Header */}
      <div className="change-panel-header">
        <div className="change-panel-title">
          {panelMode === 'diff' && selectedChange ? (
            <button className="change-back-btn" onClick={handleBack} title="목록으로">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
            </button>
          ) : (
            <span className="change-panel-icon">📋</span>
          )}
          <span>{panelMode === 'diff' ? '변경 검토' : '변경 제안'}</span>
          {hasPending && (
            <span className="change-count-badge">{pendingCount()}</span>
          )}
        </div>
        <div className="change-panel-actions">
          {panelMode === 'list' && hasChanges && (
            <>
              <button
                className="change-header-btn"
                onClick={handleClear}
                title="모든 변경 초기화"
              >
                🗑️
              </button>
              <button
                className="change-header-btn"
                onClick={onClose}
                title="패널 닫기"
              >
                ✕
              </button>
            </>
          )}
          {panelMode === 'diff' && (
            <button className="change-header-btn" onClick={handleBack}>
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Bulk Actions (only in list mode when pending changes exist) */}
      {panelMode === 'list' && hasPending && (
        <div className="change-bulk-actions">
          <button
            className="bulk-action-btn reject-all"
            onClick={handleRejectAll}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            모두 거절 ({pendingCount()})
          </button>
          <button
            className="bulk-action-btn approve-all"
            onClick={handleApproveAll}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            모두 승인 ({pendingCount()})
          </button>
        </div>
      )}

      {/* Content */}
      <div className="change-panel-content">
        {!hasChanges ? (
          <div className="change-panel-empty">
            <div className="change-empty-icon">📋</div>
            <div className="change-empty-text">제안된 변경사항이 없습니다</div>
            <div className="change-empty-hint">
              AI가 코드 변경을 제안하면 여기에 표시됩니다
            </div>
          </div>
        ) : panelMode === 'diff' && selectedChange ? (
          <DiffViewer
            change={selectedChange}
            onApprove={handleApproveChange}
            onReject={handleRejectChange}
            height="100%"
          />
        ) : (
          <div className="change-list">
            <div className="change-list-summary">
              총 <strong>{changes.length}</strong>개 변경{' · '}
              <span className="summary-pending">{pendingCount()} 검토 대기</span>
              {' · '}
              <span className="summary-approved">{useChangeStore.getState().approvedCount()} 승인됨</span>
            </div>
            <div className="change-list-items">
              {changes.map((change) => (
                <ChangeCard
                  key={change.id}
                  change={change}
                  isSelected={change.id === selectedChangeId}
                  onClick={selectChange}
                  onApprove={handleApproveChange}
                  onReject={handleRejectChange}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/* ─── Hook: ChangePanel toggle ─────────────────────────────── */

export function useChangePanel() {
  const { panelVisible, setPanelVisible } = useChangeStore();

  const toggleChangePanel = useCallback(() => {
    setPanelVisible(!panelVisible);
  }, [panelVisible, setPanelVisible]);

  return { changePanelVisible: panelVisible, toggleChangePanel };
}

export default ChangePanel;
