import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PersistentAgencyPanel } from './PersistentAgencyPanel.tsx';
import {
  createAgencyObjective,
  fetchAgencyObjectives,
  fetchAgencyStatus,
  pauseAgency,
  resumeAgency,
} from './persistentAgencyApi';

vi.mock('./persistentAgencyApi', () => ({
  createAgencyObjective: vi.fn(),
  fetchAgencyObjectives: vi.fn(),
  fetchAgencyStatus: vi.fn(),
  pauseAgency: vi.fn(),
  resumeAgency: vi.fn(),
}));

const status = {
  project_id: '/workspace/Ssak-Ai',
  enabled: true,
  paused: false,
  scheduler: { should_wake: true, reason: 'objective_ready', delay_seconds: 0, objective_id: 'objective-1' },
  context_text: '[summary] Durable context is ready',
  context_event_ids: [12, 14],
  objective_task_ids: ['task-1'],
};

const objective = {
  objective_id: 'objective-1',
  project_id: status.project_id,
  title: 'Index the repository',
  description: 'Build durable context',
  priority: 4,
  status: 'pending' as const,
  trajectory_id: 'main',
  created_at: '2026-08-28T00:00:00Z',
  updated_at: '2026-08-28T00:00:00Z',
};

describe('PersistentAgencyPanel', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    vi.mocked(fetchAgencyStatus).mockResolvedValue(status);
    vi.mocked(fetchAgencyObjectives).mockResolvedValue([objective]);
    vi.mocked(createAgencyObjective).mockResolvedValue({ ...objective, objective_id: 'objective-2', title: 'Run checks' });
    vi.mocked(pauseAgency).mockResolvedValue({ project_id: status.project_id, paused: true });
    vi.mocked(resumeAgency).mockResolvedValue({ project_id: status.project_id, paused: false });
  });

  it('renders durable status and submits a trimmed objective', async () => {
    render(<PersistentAgencyPanel />);

    expect(await screen.findByRole('heading', { name: 'Persistent Agency' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Objective ready');
    expect(screen.getByText('[summary] Durable context is ready')).toBeInTheDocument();
    expect(screen.getByText('Index the repository')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Objective title'), { target: { value: '  Run checks  ' } });
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Verify the harness' } });
    fireEvent.click(screen.getByRole('button', { name: 'Queue objective' }));

    await waitFor(() => expect(createAgencyObjective).toHaveBeenCalledWith('Run checks', 'Verify the harness', 0));
    expect(await screen.findByText('Objective queued.')).toBeInTheDocument();
  });

  it('pauses and resumes the persistent scheduler', async () => {
    vi.mocked(fetchAgencyStatus)
      .mockResolvedValueOnce(status)
      .mockResolvedValueOnce({ ...status, paused: true, scheduler: { ...status.scheduler, should_wake: false, reason: 'paused' } })
      .mockResolvedValueOnce(status);
    render(<PersistentAgencyPanel />);
    await screen.findByText('Objective ready');

    fireEvent.click(screen.getByRole('button', { name: 'Pause agency' }));
    await waitFor(() => expect(pauseAgency).toHaveBeenCalledOnce());
    expect(await screen.findByText('Agency paused.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Resume agency' }));
    await waitFor(() => expect(resumeAgency).toHaveBeenCalledOnce());
  });

  it('shows a recoverable error when the snapshot cannot load', async () => {
    vi.mocked(fetchAgencyStatus).mockRejectedValueOnce(new Error('Agency API unavailable'));

    render(<PersistentAgencyPanel />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Agency API unavailable');
    expect(screen.getByRole('button', { name: 'Retry agency status' })).toBeInTheDocument();
  });

  it('disables controls while unavailable', async () => {
    vi.mocked(fetchAgencyStatus).mockResolvedValueOnce({ ...status, enabled: false });

    render(<PersistentAgencyPanel />);

    expect(await screen.findByText('Unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pause agency' })).toBeDisabled();
    expect(screen.getByLabelText('Objective title')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Queue objective' })).toBeDisabled();
  });

  it('shows the submitting state until the objective is accepted', async () => {
    let resolveCreate: ((value: typeof objective) => void) | undefined;
    vi.mocked(createAgencyObjective).mockReturnValueOnce(new Promise(resolve => {
      resolveCreate = resolve;
    }));
    render(<PersistentAgencyPanel />);
    await screen.findByText('Objective ready');

    fireEvent.change(screen.getByLabelText('Objective title'), { target: { value: 'Long-running objective' } });
    fireEvent.click(screen.getByRole('button', { name: 'Queue objective' }));

    expect(await screen.findByRole('button', { name: 'Queueing…' })).toBeDisabled();
    resolveCreate?.({ ...objective, objective_id: 'objective-2' });
    expect(await screen.findByText('Objective queued.')).toBeInTheDocument();
  });
});
