/**
 * OutputPanel — Scrollable log output viewer
 * ===========================================
 * Displays structured output logs from tools, builds, agents, etc.
 * Supports source filtering, level-based color coding, auto-scroll,
 * and entry timestamps. Inspired by VS Code's Output panel.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useOutputStore, OUTPUT_SOURCES, type OutputSource, type OutputLevel } from '../../stores/outputStore';

/* ─── Level color mapping ──────────────────────────────────── */

const LEVEL_COLORS: Record<OutputLevel, { bg: string; text: string; dot: string }> = {
  info:    { bg: 'transparent',          text: '#c0caf5', dot: '#7aa2f7' },
  success: { bg: 'rgba(80,200,120,0.08)', text: '#9ece6a', dot: '#9ece6a' },
  warn:    { bg: 'rgba(224,175,104,0.1)', text: '#e0af68', dot: '#e0af68' },
  error:   { bg: 'rgba(247,118,142,0.1)', text: '#f7768e', dot: '#f7768e' },
  debug:   { bg: 'transparent',          text: '#7c82a8', dot: '#7c82a8' },
};

/* ─── Source options ───────────────────────────────────────── */

const SOURCE_OPTIONS: Array<{ value: OutputSource | '__all__'; label: string }> = [
  { value: '__all__', label: 'All' },
  ...Object.values(OUTPUT_SOURCES).map(s => ({ value: s as OutputSource, label: s })),
];

/* ─── Format timestamp ─────────────────────────────────────── */

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '--:--:--';
  }
}

/* ─── OutputPanel Component ────────────────────────────────── */

const OutputPanel: React.FC = () => {
  const { entries, activeSource, clearOutput, setActiveSource } = useOutputStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Filter entries by active source
  const filteredEntries = activeSource
    ? entries.filter(e => e.source === activeSource)
    : entries;

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filteredEntries.length, autoScroll]);

  // Detect manual scroll to disable auto-scroll
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 40;
    if (isNearBottom !== autoScroll) {
      setAutoScroll(isNearBottom);
    }
  }, [autoScroll]);

  return (
    <div className="output-panel">
      {/* ── Toolbar ────────────────────────────────────────── */}
      <div className="output-toolbar">
        <div className="output-source-filter">
          {SOURCE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              className={`output-filter-btn ${activeSource === opt.value || (opt.value === '__all__' && !activeSource) ? 'active' : ''}`}
              onClick={() => setActiveSource(opt.value === '__all__' ? null : opt.value)}
              aria-label={opt.label === 'All' ? '전체 출력 소스' : `${opt.label} 소스 필터`}
              aria-pressed={activeSource === opt.value || (opt.value === '__all__' && !activeSource)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="output-actions">
          <button
            className={`output-action-btn ${autoScroll ? 'active' : ''}`}
            onClick={() => setAutoScroll(!autoScroll)}
            title="Auto-scroll"
            aria-label={autoScroll ? '자동 스크롤 켜짐' : '자동 스크롤 꺼짐'}
            aria-pressed={autoScroll}
          >
            📜
          </button>
          <button
            className="output-action-btn"
            onClick={clearOutput}
            title="Clear output"
            aria-label="출력 지우기"
          >
            🗑️
          </button>
        </div>
      </div>

      {/* ── Log Entries ────────────────────────────────────── */}
      <div
        className="output-entries"
        ref={scrollRef}
        onScroll={handleScroll}
      >
        {filteredEntries.length === 0 ? (
          <div className="output-empty">
            <span>No output yet</span>
          </div>
        ) : (
          filteredEntries.map(entry => {
            const colors = LEVEL_COLORS[entry.level];
            return (
              <div
                key={entry.id}
                className="output-entry"
                style={{ background: colors.bg }}
              >
                <span className="output-entry-time" style={{ color: colors.dot }}>
                  {formatTime(entry.timestamp)}
                </span>
                <span className="output-entry-level" style={{ color: colors.dot }}>
                  {entry.level === 'error' ? '✕' : entry.level === 'warn' ? '⚠' : entry.level === 'success' ? '✓' : '·'}
                </span>
                <span className="output-entry-source" style={{ color: colors.text, opacity: 0.5 }}>
                  [{entry.source}]
                </span>
                <span className="output-entry-message" style={{ color: colors.text }}>
                  {entry.message}
                </span>
              </div>
            );
          })
        )}
      </div>

      {/* ── Footer stats ───────────────────────────────────── */}
      <div className="output-footer">
        <span>{filteredEntries.length} entries</span>
        {activeSource && <span> · filtered by {activeSource}</span>}
      </div>
    </div>
  );
};

export default OutputPanel;
