import React, { useMemo, useState } from 'react';
import { z } from 'zod';
import snapshotJson from '../data/mutation-snapshot.json';

const targetSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  file: z.string().min(1),
  score: z.number().min(0).max(100),
  killed: z.number().int().min(0),
  survived: z.number().int().min(0),
  noCoverage: z.number().int().min(0),
  lastMeasuredAt: z.string().datetime(),
});

const timelineEntrySchema = z.object({
  phase: z.string().min(1),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  summary: z.string().min(1),
  score: z.number().min(0).max(100),
});

const mutationSnapshotSchema = z.object({
  schemaVersion: z.literal(1),
  kind: z.literal('historical-snapshot'),
  capturedAt: z.string().datetime(),
  lastMeasuredAt: z.string().datetime(),
  source: z.string().min(1),
  sourceCommit: z.string().regex(/^[0-9a-f]{40}$/),
  breakThreshold: z.number().int().min(0).max(100),
  scopeNote: z.string().min(1),
  targets: z.array(targetSchema).min(1),
  timeline: z.array(timelineEntrySchema).min(1),
});

export type MutationTarget = z.infer<typeof targetSchema>;
export type MutationSnapshot = z.infer<typeof mutationSnapshotSchema>;
export type TimelineEntry = z.infer<typeof timelineEntrySchema>;
export type DecodeMutationSnapshotResult =
  | { readonly ok: true; readonly snapshot: MutationSnapshot }
  | { readonly ok: false; readonly error: string };

type FilterBand = 'all' | 'passed' | 'warning' | 'failed';

export function decodeMutationSnapshot(raw: unknown): DecodeMutationSnapshotResult {
  const parsed = mutationSnapshotSchema.safeParse(raw);
  if (parsed.success) return { ok: true, snapshot: parsed.data };
  return { ok: false, error: parsed.error.message };
}

function scoreColor(score: number): string {
  if (score >= 80) return 'var(--success-color)';
  if (score >= 60) return 'var(--warning-color)';
  return 'var(--error-color)';
}

function scoreBand(score: number): 'passed' | 'warning' | 'failed' {
  if (score >= 80) return 'passed';
  if (score >= 60) return 'warning';
  return 'failed';
}

function scoreLabel(score: number): string {
  if (score >= 80) return 'High score';
  if (score >= 60) return 'Moderate score';
  return 'Low score';
}

function formatInstant(value: string): string {
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(new Date(value));
}

function isStale(snapshot: MutationSnapshot, nowMs: number): boolean {
  const measuredMs = Date.parse(snapshot.lastMeasuredAt);
  return Number.isNaN(measuredMs) || nowMs - measuredMs > 30 * 24 * 60 * 60 * 1000;
}

function average(targets: readonly MutationTarget[]): number {
  return targets.reduce((sum, target) => sum + target.score, 0) / targets.length;
}

const panelStyle: React.CSSProperties = {
  padding: 'var(--space-5)',
  marginBottom: 'var(--space-5)',
};

const metricRowStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 'var(--space-4)',
};

const monoValueStyle: React.CSSProperties = {
  color: 'var(--text-primary)',
  fontFamily: 'var(--font-mono)',
  fontWeight: 600,
};

function SourceProvenance({ snapshot, stale }: {
  snapshot: MutationSnapshot;
  stale: boolean;
}): React.JSX.Element {
  return (
    <section className="glass-panel" style={panelStyle} aria-labelledby="mutation-source">
      <h3 id="mutation-source">Snapshot provenance</h3>
      <p role="status" style={{ color: stale ? 'var(--warning-color)' : 'var(--text-secondary)' }}>
        {stale ? 'Historical snapshot: stale' : 'Historical snapshot'} · last measurement{' '}
        {formatInstant(snapshot.lastMeasuredAt)} · captured {formatInstant(snapshot.capturedAt)}
      </p>
      <dl>
        <div>
          <dt>Source</dt>
          <dd>{snapshot.source}</dd>
        </div>
        <div>
          <dt>Source commit</dt>
          <dd>
            <code>{snapshot.sourceCommit}</code>
          </dd>
        </div>
      </dl>
      <p style={{ color: 'var(--text-secondary)' }}>{snapshot.scopeNote}</p>
    </section>
  );
}

function SummaryPanel({ snapshot }: { snapshot: MutationSnapshot }): React.JSX.Element {
  const { targets, breakThreshold } = snapshot;
  const totalKilled = targets.reduce((sum, target) => sum + target.killed, 0);
  const totalSurvived = targets.reduce((sum, target) => sum + target.survived, 0);
  const totalNoCoverage = targets.reduce((sum, target) => sum + target.noCoverage, 0);
  const allMet = targets.every(target => target.score >= breakThreshold);

  return (
    <section className="glass-panel" style={panelStyle} aria-labelledby="mutation-summary">
      <h3 id="mutation-summary">Recorded aggregate</h3>
      <div style={metricRowStyle}>
        <div>
          <div style={{ ...monoValueStyle, fontSize: 'var(--text-3xl)', color: scoreColor(average(targets)) }}>
            {average(targets).toFixed(1)}%
          </div>
          <p>average of {targets.length} preserved targets</p>
        </div>
        <div>
          <div style={monoValueStyle}>{totalKilled} killed</div>
          <div style={monoValueStyle}>{totalSurvived} survived</div>
          <div style={monoValueStyle}>{totalNoCoverage} no coverage</div>
        </div>
        <div>
          <div style={{ color: allMet ? 'var(--success-color)' : 'var(--error-color)', fontWeight: 600 }}>
            {allMet ? 'Recorded threshold met' : 'Recorded threshold not met'}
          </div>
          <p>snapshot break threshold: {breakThreshold}% · not a current CI result</p>
        </div>
      </div>
    </section>
  );
}

function TargetCard({ target, breakThreshold }: {
  target: MutationTarget;
  breakThreshold: number;
}): React.JSX.Element {
  const total = target.killed + target.survived + target.noCoverage;
  const thresholdMet = target.score >= breakThreshold;
  return (
    <article className="glass-panel" style={{ padding: 'var(--space-5)' }}>
      <header style={{ marginBottom: 'var(--space-3)' }}>
        <h4>{target.name}</h4>
        <p style={{ color: scoreColor(target.score), fontWeight: 600 }}>
          {scoreLabel(target.score)} · {target.score.toFixed(1)}%
        </p>
        <code style={{ display: 'block', color: 'var(--text-muted)' }}>{target.file}</code>
      </header>
      <div style={metricRowStyle}>
        <span>{target.killed} killed</span>
        <span>{target.survived} survived</span>
        <span>{target.noCoverage} no coverage</span>
        <span>{total} total mutants</span>
      </div>
      <p style={{ marginTop: 'var(--space-3)', color: 'var(--text-secondary)' }}>
        {thresholdMet ? 'Threshold met' : 'Threshold not met'} at the recorded time ({breakThreshold}%). Last
        measured {formatInstant(target.lastMeasuredAt)}.
      </p>
    </article>
  );
}

function Timeline({ entries }: { entries: readonly TimelineEntry[] }): React.JSX.Element {
  return (
    <section className="glass-panel" style={{ padding: 'var(--space-5)', marginTop: 'var(--space-5)' }}>
      <h3>Recorded improvement timeline</h3>
      <ol style={{ listStyle: 'none', padding: 0 }}>
        {entries.map(entry => (
          <li key={`${entry.date}-${entry.phase}`} style={{ marginBottom: 'var(--space-4)' }}>
            <span style={{ color: 'var(--text-muted)' }}>{entry.date} · {entry.phase}</span>
            <div>
              <strong style={{ color: scoreColor(entry.score), fontFamily: 'var(--font-mono)' }}>
                {entry.score.toFixed(1)}%
              </strong>
              <span> {entry.summary}</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function MutationDashboardView({ snapshot, nowMs }: {
  snapshot: MutationSnapshot;
  nowMs: number;
}): React.JSX.Element {
  const [filterBand, setFilterBand] = useState<FilterBand>('all');
  const filtered = useMemo(
    () => filterBand === 'all'
      ? snapshot.targets
      : snapshot.targets.filter(target => scoreBand(target.score) === filterBand),
    [filterBand, snapshot.targets],
  );
  const bands = ['all', 'passed', 'warning', 'failed'] as const;

  return (
    <div className="page-container" style={{ maxWidth: 'var(--content-wide)' }}>
      <header className="page-header">
        <div className="page-header-hero">
          <div className="hero-eyebrow">MUTATION TEST</div>
          <h2>Mutation test history</h2>
          <p className="page-subtitle">
            Preserved Stryker measurements with source provenance and freshness. This page does not claim a
            live CI gate result.
          </p>
        </div>
      </header>
      <SourceProvenance snapshot={snapshot} stale={isStale(snapshot, nowMs)} />
      <SummaryPanel snapshot={snapshot} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
        {bands.map(band => (
          <button
            key={band}
            type="button"
            className={`example-chip ${filterBand === band ? 'active' : ''}`}
            onClick={() => setFilterBand(band)}
          >
            {band}
          </button>
        ))}
      </div>
      <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
        {filtered.map(target => (
          <TargetCard key={target.id} target={target} breakThreshold={snapshot.breakThreshold} />
        ))}
      </div>
      {filtered.length === 0 && <p>No preserved target matches this filter.</p>}
      <Timeline entries={snapshot.timeline} />
    </div>
  );
}

function InvalidSnapshot({ error }: { error: string }): React.JSX.Element {
  return (
    <div className="page-container">
      <header className="page-header">
        <h2>Mutation snapshot unavailable</h2>
      </header>
      <section className="glass-panel" style={panelStyle} role="alert">
        <p>The bundled mutation snapshot failed validation, so no score is displayed.</p>
        <pre>{error}</pre>
      </section>
    </div>
  );
}

const decoded = decodeMutationSnapshot(snapshotJson);

function MutationDashboardPage(): React.JSX.Element {
  const [nowMs] = useState(() => Date.now());

  if (!decoded.ok) return <InvalidSnapshot error={decoded.error} />;
  return <MutationDashboardView snapshot={decoded.snapshot} nowMs={nowMs} />;
}

export default MutationDashboardPage;
