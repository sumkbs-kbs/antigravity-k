/**
 * LocalHistoryTimeline — Vertical timeline brush for file snapshots
 * ===================================================================
 * Shows all snapshots for a selected file as a chronological timeline.
 * Click dots to select/deselect for comparison, with visual indicators
 * for snapshot source (auto, manual, ai_change, git_commit).
 */

import React, { useCallback, useMemo, useRef, useEffect } from 'react';
import { useLocalHistoryStore, type FileSnapshot, type SnapshotSource } from '../../stores/localHistoryStore';

/* ─── Source config ─────────────────────────────────────────── */

const SOURCE_CONFIG: Record<SnapshotSource, { icon: string; label: string; color: string }> = {
  auto:       { icon: '🔄', label: '자동 저장', color: '#565f89' },
  manual:     { icon: '💾', label: '수동 저장', color: '#7aa2f7' },
  ai_change:  { icon: '🤖', label: 'AI 변경', color: '#bb9af7' },
  git_commit: { icon: '🐙', label: 'Git 커밋', color: '#9ece6a' },
};

/* ─── Format helpers ────────────────────────────────────────── */

function formatTime(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const diff = now.getTime() - ts;

  if (diff < 60000) return '방금 전';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}분 전`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}시간 전`;

  return d.toLocaleDateString('ko-KR', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

/* ─── Timeline Dot ──────────────────────────────────────────── */

interface TimelineDotProps {
  snapshot: FileSnapshot;
  isSelected: boolean;
  isCompareA: boolean;
  isCompareB: boolean;
  onClick: (id: string) => void;
  onCompareA: (id: string) => void;
  onCompareB: (id: string) => void;
}

const TimelineDot: React.FC<TimelineDotProps> = React.memo(({
  snapshot,
  isSelected,
  isCompareA,
  isCompareB,
  onClick,
  onCompareA,
  onCompareB,
}) => {
  const cfg = SOURCE_CONFIG[snapshot.source] || SOURCE_CONFIG.auto;
  const isCompared = isCompareA || isCompareB;

  return (
    <div
      className={`timeline-dot-row ${isCompared ? 'compared' : ''} ${isSelected ? 'selected' : ''}`}
      onClick={() => onClick(snapshot.id)}
      role="button"
      tabIndex={0}
    >
      {/* Timeline line + dot */}
      <div className="timeline-dot-line">
        <div
          className={`timeline-dot ${isCompared ? 'active' : ''}`}
          style={{
            background: isCompared ? cfg.color : 'var(--glass-border)',
            borderColor: isCompared ? cfg.color : 'var(--glass-border)',
            boxShadow: isCompared ? `0 0 6px ${cfg.color}` : 'none',
          }}
        >
          {isCompareA && <span className="timeline-compare-label a">A</span>}
          {isCompareB && <span className="timeline-compare-label b">B</span>}
        </div>
      </div>

      {/* Snapshot info */}
      <div className="timeline-dot-info">
        <div className="timeline-dot-time">{formatTime(snapshot.timestamp)}</div>
        <div className="timeline-dot-meta">
          <span className="timeline-dot-source" style={{ color: cfg.color }}>
            {cfg.icon} {cfg.label}
          </span>
          {snapshot.label && (
            <span className="timeline-dot-label">{snapshot.label}</span>
          )}
          <span className="timeline-dot-size">{formatSize(snapshot.size)}</span>
        </div>
      </div>

      {/* Compare actions */}
      <div className="timeline-dot-actions" onClick={e => e.stopPropagation()}>
        {!isCompareA && (
          <button
            className="timeline-compare-btn"
            onClick={() => onCompareA(snapshot.id)}
            title="A로 선택"
          >
            A
          </button>
        )}
        {!isCompareB && (
          <button
            className="timeline-compare-btn"
            onClick={() => onCompareB(snapshot.id)}
            title="B로 선택"
          >
            B
          </button>
        )}
      </div>
    </div>
  );
});
TimelineDot.displayName = 'TimelineDot';

/* ─── Timeline Component ───────────────────────────────────── */

const LocalHistoryTimeline: React.FC = () => {
  const {
    selectedFile, snapshots, compareIds,
    setComparePair, getSnapshotsForFile,
  } = useLocalHistoryStore();

  const fileSnapshots = useMemo(
    () => selectedFile ? getSnapshotsForFile(selectedFile) : [],
    [selectedFile, getSnapshotsForFile],
  );

  // Sort by timestamp descending (newest first)
  const sortedSnapshots = useMemo(
    () => [...fileSnapshots].sort((a, b) => b.timestamp - a.timestamp),
    [fileSnapshots],
  );

  const [compareA, compareB] = compareIds;
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to top when file changes
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = 0;
  }, [selectedFile]);

  const handleClick = useCallback((id: string) => {
    // Single click: toggle as B (most recent comparison)
    setComparePair(compareA, compareB === id ? null : id);
  }, [compareA, compareB, setComparePair]);

  const handleCompareA = useCallback((id: string) => {
    setComparePair(compareIds[0] === id ? null : id, compareIds[1]);
  }, [compareIds, setComparePair]);

  const handleCompareB = useCallback((id: string) => {
    setComparePair(compareIds[0], compareIds[1] === id ? null : id);
  }, [compareIds, setComparePair]);

  if (!selectedFile || sortedSnapshots.length === 0) {
    return (
      <div className="timeline-empty">
        <span className="timeline-empty-icon">📜</span>
        <span>파일을 선택하면 변경 내역이 표시됩니다</span>
      </div>
    );
  }

  return (
    <div className="local-history-timeline">
      <div className="timeline-header">
        <span className="timeline-title">📜 Timeline</span>
        <span className="timeline-count">{sortedSnapshots.length} snapshots</span>
      </div>
      <div className="timeline-list" ref={listRef}>
        {sortedSnapshots.map(snap => (
          <TimelineDot
            key={snap.id}
            snapshot={snap}
            isSelected={snap.id === compareA || snap.id === compareB}
            isCompareA={snap.id === compareA}
            isCompareB={snap.id === compareB}
            onClick={handleClick}
            onCompareA={handleCompareA}
            onCompareB={handleCompareB}
          />
        ))}
      </div>
    </div>
  );
};

export default LocalHistoryTimeline;
