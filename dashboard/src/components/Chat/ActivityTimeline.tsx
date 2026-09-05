/**
 * ActivityTimeline — Antigravity-style live activity strip
 * ========================================================
 * Collapsed by default: shows the latest few activity labels as chips
 * ("파일 수정함 · 파일 읽음 · 명령 실행") like the Antigravity agent
 * feed. Expanding reveals per-item rows with status dots, mono detail
 * and relative time. Data comes from activityStore (ws events).
 */

import React, { useState } from 'react';
import { useActivityStore, type ActivityItem } from '../../stores/activityStore';

const KIND_ICONS: Record<ActivityItem['kind'], string> = {
  tool: '⚙',
  file_read: '↺',
  file_edit: '✏',
  error: '⚠',
  plan: '≡',
};

function relativeTime(at: number, now: number): string {
  const seconds = Math.max(0, Math.round((now - at) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h`;
}

export const ActivityTimeline: React.FC = () => {
  const items = useActivityStore((s) => s.items);
  const [expanded, setExpanded] = useState<boolean>(false);

  if (items.length === 0) return null;

  const now = Date.now();
  const chipLabels: string[] = [];
  for (let i = items.length - 1; i >= 0 && chipLabels.length < 3; i -= 1) {
    if (!chipLabels.includes(items[i].label)) chipLabels.push(items[i].label);
  }
  const runningCount = items.filter((i) => i.status === 'running').length;
  const visible = expanded ? items.slice(-12) : [];

  return (
    <div className="agk-activity" data-testid="activity-timeline">
      <button
        type="button"
        className="activity-header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="activity-chips">
          {chipLabels.map((label) => (
            <span key={label} className="activity-chip">
              {label}
            </span>
          ))}
        </span>
        <span className="activity-count">
          활동 {items.length}개{runningCount > 0 ? ` · ${runningCount}개 실행 중` : ''}
        </span>
        <span className={`env-chevron ${expanded ? 'open' : ''}`}>⌄</span>
      </button>

      {expanded && (
        <div className="activity-rows">
          {visible.map((item) => (
            <div key={item.id} className={`activity-row status-${item.status}`}>
              <span className="activity-row-icon">{KIND_ICONS[item.kind]}</span>
              <span className="activity-row-label">{item.label}</span>
              {item.detail && <span className="activity-row-detail">{item.detail}</span>}
              <span className="activity-row-time">{relativeTime(item.at, now)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ActivityTimeline;
