/**
 * MutationDashboardPage — Mutation Score Dashboard
 * =================================================
 * Visualizes Stryker mutation testing scores across all stores,
 * CI/CD break thresholds, improvement history, and recommendations.
 */

import React, { useMemo, useState } from 'react';

/* ─── Data ──────────────────────────────────────────────────────── */

interface StoreData {
  id: string;
  name: string;
  file: string;
  score: number;
  previousScore: number;
  killed: number;
  survived: number;
  noCoverage: number;
  improvedBy: number;
  ciBreakThreshold: number;
  status: 'passed' | 'warning' | 'failed';
}

const STORES: StoreData[] = [
  {
    id: 'pluginRegistry',
    name: 'pluginRegistry',
    file: 'src/plugin/pluginRegistry.ts',
    score: 86.78,
    previousScore: 69.42,
    killed: 105,
    survived: 13,
    noCoverage: 3,
    improvedBy: 17.36,
    ciBreakThreshold: 50,
    status: 'passed',
  },
  {
    id: 'agentMonitorStore',
    name: 'agentMonitorStore',
    file: 'src/stores/agentMonitorStore.ts',
    score: 78.13,
    previousScore: 74.22,
    killed: 100,
    survived: 26,
    noCoverage: 2,
    improvedBy: 3.91,
    ciBreakThreshold: 50,
    status: 'passed',
  },
  {
    id: 'localHistoryStore',
    name: 'localHistoryStore',
    file: 'src/stores/localHistoryStore.ts',
    score: 64.52,
    previousScore: 58.71,
    killed: 100,
    survived: 28,
    noCoverage: 27,
    improvedBy: 5.81,
    ciBreakThreshold: 50,
    status: 'passed',
  },
];

const CI_BREAK_THRESHOLD = 50;

/* ─── Helpers ────────────────────────────────────────────────────── */

function scoreColor(score: number): string {
  if (score >= 80) return '#10b981';
  if (score >= 60) return '#fbbf24';
  return '#ef4444';
}

function scoreBg(score: number): string {
  if (score >= 80) return 'rgba(16, 185, 129, 0.1)';
  if (score >= 60) return 'rgba(251, 191, 36, 0.1)';
  return 'rgba(239, 68, 68, 0.1)';
}

function scoreLabel(score: number): string {
  if (score >= 80) return '🟢 Excellent';
  if (score >= 60) return '🟡 Moderate';
  return '🔴 Needs Work';
}

/* ─── Progress Ring Component ───────────────────────────────────── */

const ProgressRing: React.FC<{ score: number; size?: number; strokeWidth?: number }> = ({
  score, size = 100, strokeWidth = 8,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = scoreColor(score);

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.8s ease' }}
      />
      <text
        x="50%" y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        fill={color}
        fontSize={22}
        fontWeight={700}
        fontFamily="'JetBrains Mono', monospace"
        style={{ transform: 'rotate(90deg)', transformOrigin: 'center' }}
      >
        {score.toFixed(1)}%
      </text>
    </svg>
  );
};

/* ─── Store Score Card ──────────────────────────────────────────── */

const StoreCard: React.FC<{ store: StoreData }> = ({ store }) => {
  const [expanded, setExpanded] = useState(false);
  const color = scoreColor(store.score);
  const total = store.killed + store.survived + store.noCoverage;

  return (
    <div
      className="glass-panel"
      style={{
        padding: 0,
        overflow: 'hidden',
        transition: 'all 0.25s ease',
        cursor: 'pointer',
      }}
      onClick={() => setExpanded(!expanded)}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = `${color}40`; }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = ''; }}
    >
      {/* Main content */}
      <div style={{ padding: 20, display: 'flex', gap: 20, alignItems: 'center' }}>
        {/* Progress ring */}
        <div style={{ flexShrink: 0 }}>
          <ProgressRing score={store.score} size={96} strokeWidth={7} />
        </div>

        {/* Details */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <strong style={{ fontSize: 15, color: 'var(--text-primary)' }}>
              {store.name}
            </strong>
            <span
              style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                background: scoreBg(store.score), color,
                fontWeight: 600, border: `1px solid ${color}30`,
              }}
            >
              {scoreLabel(store.score)}
            </span>
          </div>

          <code style={{
            fontSize: 11, color: 'var(--text-muted)',
            fontFamily: "'JetBrains Mono', monospace",
            display: 'block', marginBottom: 10,
          }}>
            {store.file}
          </code>

          {/* Stats row */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
            <StatBadge label="Killed" value={store.killed} color="#10b981" />
            <StatBadge label="Survived" value={store.survived} color="#ef4444" />
            <StatBadge label="No Coverage" value={store.noCoverage} color="#fbbf24" />
            <StatBadge label="Total" value={total} color="var(--text-muted)" />
          </div>

          {/* Improvement */}
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
            <span>📈 </span>
            <span style={{ color: '#10b981', fontWeight: 600 }}>+{store.improvedBy.toFixed(1)}pp</span>
            <span style={{ color: 'var(--text-muted)' }}> (from {store.previousScore.toFixed(1)}%)</span>
          </div>
        </div>

        {/* Expand icon */}
        <div style={{ color: 'var(--text-muted)', fontSize: 18, flexShrink: 0 }}>
          {expanded ? '▲' : '▼'}
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div style={{
          borderTop: '1px solid var(--glass-border)',
          padding: '16px 20px',
          background: 'rgba(0,0,0,0.15)',
        }}>
          {/* Progress bar */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
              <span>Mutation Score</span>
              <span>CI Break Threshold: {CI_BREAK_THRESHOLD}%</span>
            </div>
            <div style={{ height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
              {/* Break threshold line */}
              <div style={{
                position: 'absolute', left: `${CI_BREAK_THRESHOLD}%`, top: 0, bottom: 0,
                width: 2, background: '#ef4444', zIndex: 1, opacity: 0.8,
              }} />
              {/* Score bar */}
              <div style={{
                width: `${store.score}%`, height: '100%',
                background: `linear-gradient(90deg, ${color}, ${color}88)`,
                borderRadius: 4,
                transition: 'width 0.5s ease',
              }} />
            </div>
          </div>

          {/* Detailed breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
            <div>
              <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>🧬 Mutants Breakdown</div>
              <div style={{ display: 'flex', gap: 6, height: 20 }}>
                <div
                  style={{ flex: store.killed, background: '#10b981', borderRadius: 3, opacity: 0.7 }}
                  title={`Killed: ${store.killed}`}
                />
                <div
                  style={{ flex: store.survived, background: '#ef4444', borderRadius: 3, opacity: 0.7 }}
                  title={`Survived: ${store.survived}`}
                />
                <div
                  style={{ flex: store.noCoverage, background: '#fbbf24', borderRadius: 3, opacity: 0.7 }}
                  title={`No Coverage: ${store.noCoverage}`}
                />
              </div>
              <div style={{ display: 'flex', gap: 12, marginTop: 4, color: 'var(--text-muted)', fontSize: 10 }}>
                <span>✅ Killed {store.killed}</span>
                <span>⛔ Survived {store.survived}</span>
                <span>⚠️ No cov {store.noCoverage}</span>
              </div>
            </div>
            <div>
              <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>✅ CI Status</div>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '4px 10px', borderRadius: 6,
                background: store.score >= CI_BREAK_THRESHOLD
                  ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                color: store.score >= CI_BREAK_THRESHOLD ? '#10b981' : '#ef4444',
                fontWeight: 600, fontSize: 12,
              }}>
                {store.score >= CI_BREAK_THRESHOLD ? '✅ Pass' : '❌ Fail'}
                <span style={{ opacity: 0.6, fontWeight: 400 }}>
                  (threshold: {CI_BREAK_THRESHOLD}%)
                </span>
              </div>
              <div style={{ marginTop: 6, color: 'var(--text-muted)', fontSize: 10 }}>
                Run: <code style={{ fontSize: 10 }}>npx stryker run --mutate '{store.file}'</code>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const StatBadge: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
    <span style={{
      display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
      background: color, opacity: 0.6,
    }} />
    <span style={{ color: 'var(--text-secondary)' }}>{label}:</span>
    <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
      {value}
    </span>
  </div>
);

/* ─── Summary Bar ───────────────────────────────────────────────── */

const SummaryBar: React.FC<{ stores: StoreData[] }> = ({ stores }) => {
  const avgScore = stores.reduce((sum, s) => sum + s.score, 0) / stores.length;
  const allPassed = stores.every(s => s.score >= CI_BREAK_THRESHOLD);
  const totalKilled = stores.reduce((sum, s) => sum + s.killed, 0);
  const totalSurvived = stores.reduce((sum, s) => sum + s.survived, 0);
  const totalMutants = stores.reduce((sum, s) => sum + s.killed + s.survived + s.noCoverage, 0);

  return (
    <div
      className="glass-panel"
      style={{
        padding: 20, marginBottom: 20,
        display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap',
      }}
    >
      {/* Average score */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: scoreColor(avgScore), fontFamily: "'JetBrains Mono', monospace" }}>
          {avgScore.toFixed(1)}%
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Average Score</div>
      </div>

      <div style={{ width: 1, height: 40, background: 'var(--glass-border)' }} />

      {/* CI Status */}
      <div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, fontWeight: 600,
          color: allPassed ? '#10b981' : '#ef4444',
        }}>
          {allPassed ? '✅ CI Gate: PASS' : '❌ CI Gate: FAIL'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
          All scores must be ≥ {CI_BREAK_THRESHOLD}%
        </div>
      </div>

      <div style={{ width: 1, height: 40, background: 'var(--glass-border)' }} />

      {/* Totals */}
      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: '#10b981', fontFamily: "'JetBrains Mono', monospace" }}>
            {totalKilled}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Killed</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: '#ef4444', fontFamily: "'JetBrains Mono', monospace" }}>
            {totalSurvived}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Survived</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>
            {totalMutants}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Total</div>
        </div>
      </div>

      <div style={{ width: 1, height: 40, background: 'var(--glass-border)' }} />

      {/* CI Config */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7 }}>
        <div>⚙️ CI: <code style={{ fontSize: 10 }}>.github/workflows/ci.yml</code></div>
        <div>🧪 Runner: <code style={{ fontSize: 10 }}>npx stryker run</code></div>
        <div>📊 Report: <code style={{ fontSize: 10 }}>reports/mutation/mutation.html</code></div>
      </div>
    </div>
  );
};

/* ─── Improvement Timeline ──────────────────────────────────────── */

const ImprovementTimeline: React.FC = () => {
  const timeline = [
    { phase: 'Phase 1', date: '2026-07-10', summary: 'localHistoryStore 초기 측정', score: 58.71 },
    { phase: 'Mutation 1', date: '2026-07-15', summary: '11개 테스트 추가 (trim, clearFile, getAllFiles)', score: 64.52 },
    { phase: 'Phase 2', date: '2026-07-16', summary: 'pluginRegistry 초기 측정', score: 69.42 },
    { phase: 'Mutation 2', date: '2026-07-17', summary: '14개 테스트 추가 (localStorage, onLoad/Unload, rebuildLists)', score: 86.78 },
    { phase: 'Phase 3', date: '2026-07-18', summary: 'agentMonitorStore 초기 측정', score: 74.22 },
    { phase: 'Mutation 3', date: '2026-07-21', summary: '14개 테스트 추가 (boundary, slice, prepend, nullish)', score: 78.13 },
  ];

  return (
    <div className="glass-panel" style={{ padding: 20, marginTop: 20 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
        📈 개선 타임라인
      </h3>
      <div style={{ position: 'relative', paddingLeft: 24 }}>
        {/* Timeline vertical line */}
        <div style={{
          position: 'absolute', left: 8, top: 0, bottom: 0,
          width: 2, background: 'var(--glass-border)',
        }} />
        {timeline.map((item, i) => (
          <div key={i} style={{ position: 'relative', paddingBottom: 16, paddingLeft: 16 }}>
            {/* Dot */}
            <div style={{
              position: 'absolute', left: -20, top: 4,
              width: 12, height: 12, borderRadius: '50%',
              background: scoreColor(item.score),
              border: '2px solid var(--bg-primary)',
              boxShadow: `0 0 6px ${scoreColor(item.score)}`,
            }} />
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>
              {item.date} — {item.phase}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>
              <span style={{
                fontWeight: 700, fontSize: 14, fontFamily: "'JetBrains Mono', monospace",
                color: scoreColor(item.score),
              }}>
                {item.score.toFixed(1)}%
              </span>
              <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>
                {item.summary}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ─── Main Page ─────────────────────────────────────────────────── */

const MutationDashboardPage: React.FC = () => {
  const [filterStatus, setFilterStatus] = useState<'all' | 'passed' | 'warning' | 'failed'>('all');

  const filtered = useMemo(
    () => filterStatus === 'all' ? STORES : STORES.filter(s => s.status === filterStatus),
    [filterStatus],
  );

  return (
    <div className="page-container" style={{ maxWidth: 1000 }}>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <h2>🧬 Mutation Test Dashboard <span>Stryker Score</span></h2>
        <p className="page-subtitle">
          Zustand Store 단위 변이 테스트 점수를 실시간으로 모니터링합니다.
          CI 게이트 기준: <strong style={{ color: '#ef4444' }}>{CI_BREAK_THRESHOLD}%</strong> 미만 시 실패.
        </p>
      </div>

      {/* Summary */}
      <SummaryBar stores={STORES} />

      {/* Filter chips */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['all', 'passed', 'warning', 'failed'] as const).map(status => (
          <button
            key={status}
            className={`example-chip ${filterStatus === status ? 'active' : ''}`}
            onClick={() => setFilterStatus(status)}
            style={{
              ...(filterStatus === status ? {
                background: 'rgba(124,106,239,0.12)',
                borderColor: 'var(--accent-color)',
                color: 'var(--accent-color)',
              } : {}),
              fontSize: 12, padding: '6px 14px',
            }}
          >
            {status === 'all' ? '📋 All' : status === 'passed' ? '✅ Passed' : status === 'warning' ? '🟡 Warning' : '🔴 Failed'}
          </button>
        ))}
      </div>

      {/* Store cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {filtered.map(store => (
          <StoreCard key={store.id} store={store} />
        ))}
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div style={{
          textAlign: 'center', padding: 60, color: 'var(--text-muted)',
        }}>
          <span style={{ fontSize: 48, opacity: 0.3 }}>🧬</span>
          <div style={{ marginTop: 12, fontSize: 14 }}>No stores match this filter.</div>
        </div>
      )}

      {/* Improvement Timeline */}
      <ImprovementTimeline />
    </div>
  );
};

export default MutationDashboardPage;
