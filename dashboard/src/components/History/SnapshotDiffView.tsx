/**
 * SnapshotDiffView — Compare two file snapshots
 * ===============================================
 * Uses Monaco DiffEditor to show side-by-side comparison
 * of two selected snapshots from local history.
 */

import React, { useCallback, useMemo } from 'react';
import { DiffEditor } from '@monaco-editor/react';
import type { DiffOnMount } from '@monaco-editor/react';
import { useLocalHistoryStore, type FileSnapshot } from '../../stores/localHistoryStore';

/* ─── Custom Theme ─────────────────────────────────────────── */

const SNAPSHOT_DIFF_THEME = {
  base: 'vs-dark' as const,
  inherit: true,
  rules: [],
  colors: {
    'editor.background': '#1a1b2e',
    'editor.foreground': '#c0caf5',
    'diffEditor.insertedTextBackground': '#1b3b2a',
    'diffEditor.removedTextBackground': '#3b1b1b',
    'diffEditor.insertedLineBackground': '#1b3b2a80',
    'diffEditor.removedLineBackground': '#3b1b1b80',
    'diffEditor.border': '#2d2d3d',
  },
};

/* ─── Helpers ──────────────────────────────────────────────── */

function formatSnapshotLabel(snap: FileSnapshot): string {
  const d = new Date(snap.timestamp);
  const dateStr = d.toLocaleString('ko-KR', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const sourceLabel = snap.source === 'ai_change' ? '🤖 AI' :
    snap.source === 'auto' ? '🔄 Auto' :
    snap.source === 'manual' ? '💾 Save' : '🐙 Git';
  return `${dateStr} ${sourceLabel}${snap.label ? ` — ${snap.label}` : ''}`;
}

/* ─── SnapshotDiffView ─────────────────────────────────────── */

const SnapshotDiffView: React.FC = () => {
  const { compareIds, getSnapshotById, swapComparePair } = useLocalHistoryStore();

  const snapA = useMemo(() => getSnapshotById(compareIds[0]), [compareIds[0], getSnapshotById]);
  const snapB = useMemo(() => getSnapshotById(compareIds[1]), [compareIds[1], getSnapshotById]);

  const handleMount: DiffOnMount = useCallback((diffEditor, monaco) => {
    // Only define theme once
    const existing = monaco.editor.getTheme?.('snapshot-diff-theme');
    if (!existing) monaco.editor.defineTheme('snapshot-diff-theme', SNAPSHOT_DIFF_THEME);
    monaco.editor.setTheme('snapshot-diff-theme');

    setTimeout(() => {
      try { diffEditor?.layout?.(); } catch { /* ignore */ }
    }, 50);

    const container = diffEditor.getContainerDomNode();
    if (container) {
      const observer = new ResizeObserver(() => {
        try { diffEditor?.layout?.(); } catch { /* ignore */ }
      });
      observer.observe(container);
    }
  }, []);

  if (!compareIds[0] && !compareIds[1]) {
    return (
      <div className="snapshot-diff-empty">
        <div className="snapshot-diff-empty-icon">📊</div>
        <div>비교할 스냅샷을 타임라인에서 선택하세요</div>
        <div className="snapshot-diff-empty-hint">
          A/B 버튼으로 두 지점을 선택하면 차이를 확인할 수 있습니다
        </div>
      </div>
    );
  }

  if ((compareIds[0] && !snapA) || (compareIds[1] && !snapB)) {
    return <div className="snapshot-diff-empty">선택한 스냅샷을 찾을 수 없습니다</div>;
  }

  const original = compareIds[0] ? snapA!.content : '';
  const modified = compareIds[1] ? snapB!.content : '';
  const language = snapB?.fileName ? (
    snapB.fileName.split('.').pop()?.toLowerCase() || 'plaintext'
  ) : 'plaintext';

  const hasBoth = !!(compareIds[0] && compareIds[1]);

  return (
    <div className="snapshot-diff-container">
      {/* Diff Header */}
      <div className="snapshot-diff-header">
        <div className="snapshot-diff-labels">
          <span className="snapshot-diff-label original">
            <span className="snapshot-diff-badge a">A</span>
            {snapA ? formatSnapshotLabel(snapA) : '빈 상태'}
          </span>
          {hasBoth && (
            <button className="snapshot-swap-btn" onClick={swapComparePair} title="Swap A/B">
              ⇄
            </button>
          )}
          <span className="snapshot-diff-label modified">
            <span className="snapshot-diff-badge b">B</span>
            {snapB ? formatSnapshotLabel(snapB) : '빈 상태'}
          </span>
        </div>
        {hasBoth && (
          <span className="snapshot-diff-path">
            {snapB!.filePath}
          </span>
        )}
      </div>

      {/* Diff Editor */}
      <div className="snapshot-diff-editor">
        <DiffEditor
          original={original}
          modified={modified}
          language={language}
          theme="snapshot-diff-theme"
          onMount={handleMount}
          options={{
            fontSize: 12,
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
              불러오는 중...
            </div>
          }
        />
      </div>
    </div>
  );
};

export default SnapshotDiffView;
