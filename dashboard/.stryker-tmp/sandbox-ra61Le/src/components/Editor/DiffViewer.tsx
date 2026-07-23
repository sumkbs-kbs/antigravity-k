/**
 * DiffViewer — Monaco Diff Editor for proposed file changes
 * ==========================================================
 * Uses @monaco-editor/react's DiffEditor to show side-by-side
 * or unified diff of proposed file changes.
 * Supports inline accept/reject actions.
 */
// @ts-nocheck


import React, { useCallback, useRef } from 'react';
import { DiffEditor } from '@monaco-editor/react';
import type { DiffOnMount } from '@monaco-editor/react';
import { useChangeStore, ProposedChange } from '../../stores/changeStore';
import { useUiStore } from '../../stores/uiStore';

/* ─── Custom Theme ─────────────────────────────────────────── */

const DIFF_THEME = {
  base: 'vs-dark' as const,
  inherit: true,
  rules: [
    { token: 'comment', foreground: '565f89' },
    { token: 'keyword', foreground: 'bb9af7' },
    { token: 'string', foreground: '9ece6a' },
    { token: 'number', foreground: 'ff9e64' },
    { token: 'type', foreground: '2ac3de' },
    { token: 'function', foreground: '7aa2f7' },
  ],
  colors: {
    'editor.background': '#1a1b2e',
    'editor.foreground': '#c0caf5',
    'editor.lineHighlightBackground': '#292e42',
    'diffEditor.insertedTextBackground': '#1b3b2a',
    'diffEditor.removedTextBackground': '#3b1b1b',
    'diffEditor.insertedLineBackground': '#1b3b2a80',
    'diffEditor.removedLineBackground': '#3b1b1b80',
    'diffEditor.border': '#2d2d3d',
    'minimap.background': '#1a1b2e',
  },
};

/* ─── Props ────────────────────────────────────────────────── */

interface DiffViewerProps {
  change: ProposedChange;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  showActions?: boolean;
  height?: string | number;
}

/* ─── Component ────────────────────────────────────────────── */

const DiffViewer: React.FC<DiffViewerProps> = ({
  change,
  onApprove,
  onReject,
  showActions = true,
  height = '100%',
}) => {
  const editorRef = useRef<any>(null);
  const { addToast } = useUiStore();

  const handleMount: DiffOnMount = useCallback((diffEditor, monaco) => {
    const editor = diffEditor.getModifiedEditor();
    editorRef.current = editor;
    monaco.editor.defineTheme('diff-theme', DIFF_THEME);
    monaco.editor.setTheme('diff-theme');

    // Auto-layout on mount
    const layout = () => {
      try { diffEditor?.layout?.(); } catch { /* ignore */ }
    };
    setTimeout(layout, 50);

    // ResizeObserver
    const container = diffEditor.getContainerDomNode();
    if (container) {
      const observer = new ResizeObserver(() => {
        try { layout(); } catch { /* ignore */ }
      });
      observer.observe(container);
    }
  }, []);

  const handleApprove = useCallback(() => {
    if (onApprove) {
      onApprove(change.id);
      addToast(`✅ 승인됨: ${change.fileName}`, 'success');
    }
  }, [change.id, change.fileName, onApprove, addToast]);

  const handleReject = useCallback(() => {
    if (onReject) {
      onReject(change.id);
      addToast(`❌ 거절됨: ${change.fileName}`, 'error');
    }
  }, [change.id, change.fileName, onReject, addToast]);

  const stats = change.diffStats;

  return (
    <div className="diff-viewer-container">
      {/* Diff Header with stats */}
      <div className="diff-viewer-header">
        <div className="diff-header-left">
          <span className="diff-file-icon">📄</span>
          <span className="diff-file-path">{change.filePath}</span>
          {change.description && (
            <span className="diff-desc">{change.description}</span>
          )}
        </div>
        <div className="diff-header-right">
          {stats && (
            <span className="diff-stats">
              <span className="diff-stat-added">+{stats.additions}</span>
              <span className="diff-stat-removed">-{stats.deletions}</span>
            </span>
          )}
          <span className={`diff-status-badge status-${change.status}`}>
            {change.status === 'pending' && '⏳ 검토 대기'}
            {change.status === 'approved' && '✅ 승인됨'}
            {change.status === 'rejected' && '❌ 거절됨'}
            {change.status === 'applied' && '✔ 적용됨'}
            {change.status === 'failed' && '⚠️ 실패'}
          </span>
        </div>
      </div>

      {/* Monaco Diff Editor */}
      <div className="diff-editor-wrapper" style={{ height: typeof height === 'number' ? height : '100%' }}>
        <DiffEditor
          original={change.originalContent}
          modified={change.newContent}
          language={change.language || 'plaintext'}
          theme="diff-theme"
          onMount={handleMount}
          options={{
            fontSize: 13,
            fontFamily: "'JetBrains Mono', monospace",
            lineNumbers: 'on',
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            readOnly: true,
            renderWhitespace: 'none',
            folding: false,
            contextmenu: false,
            overviewRulerBorder: false,
            hideCursorInOverviewRuler: true,
            smoothScrolling: true,
            automaticLayout: true,
          }}
          loading={
            <div className="diff-loading">
              <span className="spinner spinner-sm" />
              Diff 로딩 중...
            </div>
          }
        />
      </div>

      {/* Actions Bar */}
      {showActions && change.status === 'pending' && (
        <div className="diff-actions-bar">
          <button
            className="diff-action-btn reject"
            onClick={handleReject}
            title="변경 거절"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            거절
          </button>
          <button
            className="diff-action-btn approve"
            onClick={handleApprove}
            title="변경 승인"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            승인
          </button>
        </div>
      )}

      {/* Status feedback for non-pending changes */}
      {change.status !== 'pending' && (
        <div className={`diff-status-bar status-${change.status}`}>
          {change.status === 'approved' && '✅ 승인됨 — 다음 응답에서 적용됩니다'}
          {change.status === 'rejected' && '❌ 거절됨 — 변경이 취소되었습니다'}
          {change.status === 'applied' && '✔ 파일에 적용됨'}
          {change.status === 'failed' && '⚠️ 파일 적용 실패'}
        </div>
      )}
    </div>
  );
};

export default DiffViewer;
