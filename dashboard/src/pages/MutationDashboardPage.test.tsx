import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  MutationDashboardView,
  decodeMutationSnapshot,
  type MutationSnapshot,
} from './MutationDashboardPage';

const snapshot: MutationSnapshot = {
  schemaVersion: 1,
  kind: 'historical-snapshot',
  capturedAt: '2026-09-03T00:00:00Z',
  lastMeasuredAt: '2026-07-21T00:00:00Z',
  source: 'Stryker HTML report',
  sourceCommit: '6d0a24d4e6a0686693ce29a4d13a69443ae5149b',
  breakThreshold: 55,
  scopeNote: 'Fixture scope',
  targets: [
    {
      id: 'target-a',
      name: 'target-a',
      file: 'src/target-a.ts',
      score: 61.2,
      killed: 12,
      survived: 5,
      noCoverage: 3,
      lastMeasuredAt: '2026-07-21T00:00:00Z',
    },
  ],
  timeline: [
    {
      phase: 'Initial measurement',
      date: '2026-07-21',
      summary: 'First recorded run',
      score: 61.2,
    },
  ],
};

describe('MutationDashboardPage', () => {
  it('renders values and provenance from the supplied snapshot without claiming a live CI pass', () => {
    render(<MutationDashboardView snapshot={snapshot} nowMs={Date.parse('2026-09-04T00:00:00Z')} />);

    expect(screen.getAllByText('61.2%').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/12 killed/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/5 survived/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('status')).toHaveTextContent(/historical snapshot/i);
    expect(screen.getByRole('status')).toHaveTextContent(/stale/i);
    expect(screen.getByText(snapshot.sourceCommit)).toBeInTheDocument();
    expect(screen.queryByText(/ci gate: pass/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/실시간/i)).not.toBeInTheDocument();
  });

  it('rejects malformed snapshot data at the boundary', () => {
    const result = decodeMutationSnapshot({ schemaVersion: 2 });

    expect(result.ok).toBe(false);
  });
});
