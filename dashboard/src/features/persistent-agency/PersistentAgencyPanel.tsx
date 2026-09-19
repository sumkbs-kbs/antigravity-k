import { useCallback, useEffect, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';

import {
  createAgencyObjective,
  fetchAgencyObjectives,
  fetchAgencyStatus,
  pauseAgency,
  resumeAgency,
  type AgencyObjective,
  type AgencyStatus,
} from './persistentAgencyApi';

type AgencyAction = 'pause' | 'resume' | null;

const schedulerLabels: Readonly<Record<string, string>> = {
  disabled: 'Scheduler disabled',
  paused: 'Scheduler paused',
  objective_ready: 'Objective ready',
  idle_backoff: 'Idle backoff',
};

function schedulerLabel(reason: string): string {
  return schedulerLabels[reason] ?? reason;
}

function objectiveStatusLabel(objective: AgencyObjective): string {
  switch (objective.status) {
    case 'pending': return 'Pending';
    case 'claimed': return 'Claimed';
    case 'done': return 'Done';
    case 'cancelled': return 'Cancelled';
    default: return objective.status;
  }
}

export function PersistentAgencyPanel(): ReactElement {
  const [status, setStatus] = useState<AgencyStatus | null>(null);
  const [objectives, setObjectives] = useState<readonly AgencyObjective[]>([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('0');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [action, setAction] = useState<AgencyAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadSnapshot = useCallback(async (signal?: AbortSignal): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextObjectives] = await Promise.all([
        fetchAgencyStatus(signal),
        fetchAgencyObjectives(signal),
      ]);
      setStatus(nextStatus);
      setObjectives(nextObjectives);
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return;
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const initialLoad = window.setTimeout(() => void loadSnapshot(controller.signal), 0);
    const interval = window.setInterval(() => void loadSnapshot(controller.signal), 15_000);
    return () => {
      controller.abort();
      window.clearTimeout(initialLoad);
      window.clearInterval(interval);
    };
  }, [loadSnapshot]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError('Objective title is required.');
      return;
    }
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      await createAgencyObjective(trimmedTitle, description.trim(), Number(priority) || 0);
      setTitle('');
      setDescription('');
      setPriority('0');
      setNotice('Objective queued.');
      await loadSnapshot();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSubmitting(false);
    }
  };

  const handlePauseToggle = async (): Promise<void> => {
    const nextAction: AgencyAction = status?.paused === true ? 'resume' : 'pause';
    if (nextAction === null) return;
    setAction(nextAction);
    setError(null);
    setNotice(null);
    try {
      if (nextAction === 'pause') await pauseAgency();
      else await resumeAgency();
      setNotice(nextAction === 'pause' ? 'Agency paused.' : 'Agency resumed.');
      await loadSnapshot();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setAction(null);
    }
  };

  const scheduler = status?.scheduler;
  const isPaused = status?.paused === true;
  const isUnavailable = status?.enabled === false;
  const stateLabel = status === null
    ? 'Loading agency'
    : isUnavailable
      ? 'Unavailable'
      : isPaused
        ? 'Paused'
        : schedulerLabel(scheduler?.reason ?? 'disabled');

  return (
    <section className="persistent-agency-panel glass-panel" aria-labelledby="persistent-agency-title">
      <header className="persistent-agency-header">
        <div>
          <p className="hero-eyebrow">DURABLE AGENCY</p>
          <h3 id="persistent-agency-title">Persistent Agency</h3>
          <p>Queue long-running objectives and keep compact context across sessions.</p>
        </div>
        <div className="persistent-agency-actions">
          <span className={`agency-state-badge ${isUnavailable ? 'is-unavailable' : isPaused ? 'is-paused' : 'is-active'}`} role="status">
            <span className="agency-state-dot" aria-hidden="true" />
            {stateLabel}
          </span>
          <button className="btn-secondary" type="button" onClick={() => void loadSnapshot()} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh status'}
          </button>
          <button className="btn-secondary" type="button" onClick={() => void handlePauseToggle()} disabled={action !== null || status === null || isUnavailable}>
            {action === 'pause' ? 'Pausing…' : action === 'resume' ? 'Resuming…' : isPaused ? 'Resume agency' : 'Pause agency'}
          </button>
        </div>
      </header>

      {error !== null && (
        <div className="persistent-agency-feedback is-error" role="alert">
          <span>{error}</span>
          <button className="btn-ghost" type="button" onClick={() => void loadSnapshot()}>Retry agency status</button>
        </div>
      )}
      {notice !== null && <div className="persistent-agency-feedback is-notice" role="status">{notice}</div>}

      <div className="persistent-agency-grid">
        <form className="persistent-agency-form" onSubmit={(event) => void handleSubmit(event)}>
          <div className="persistent-agency-section-heading">
            <h4>Queue objective</h4>
            <span>Durable and project-scoped</span>
          </div>
          <label htmlFor="agency-objective-title">Objective title</label>
          <input id="agency-objective-title" className="text-input" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={500} disabled={isUnavailable || submitting} />
          <label htmlFor="agency-objective-description">Description</label>
          <textarea id="agency-objective-description" className="text-input persistent-agency-description" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={8_000} disabled={isUnavailable || submitting} />
          <div className="persistent-agency-form-row">
            <label htmlFor="agency-objective-priority">Priority</label>
            <input id="agency-objective-priority" className="text-input persistent-agency-priority" type="number" value={priority} onChange={(event) => setPriority(event.target.value)} min={-1_000} max={1_000} disabled={isUnavailable || submitting} />
            <button className="btn-primary" type="submit" disabled={isUnavailable || submitting}>{submitting ? 'Queueing…' : 'Queue objective'}</button>
          </div>
        </form>

        <div className="persistent-agency-context">
          <div className="persistent-agency-section-heading">
            <h4>Context projection</h4>
            <span>{status?.context_event_ids.length ?? 0} events recalled</span>
          </div>
          <pre>{status?.context_text || 'No durable context has been projected yet.'}</pre>
          <div className="persistent-agency-meta">
            <span>{scheduler?.should_wake ? 'Wake eligible' : 'No wake scheduled'}</span>
            <span>{scheduler?.delay_seconds ?? 0}s backoff</span>
            <span>{status?.objective_task_ids.length ?? 0} active task links</span>
          </div>
        </div>
      </div>

      <div className="persistent-agency-objectives">
        <div className="persistent-agency-section-heading">
          <h4>Objective history</h4>
          <span>{objectives.length} objectives</span>
        </div>
        {objectives.length === 0 ? (
          <p className="persistent-agency-empty">No objectives queued.</p>
        ) : (
          <ul>
            {objectives.map((objective) => (
              <li key={objective.objective_id}>
                <div>
                  <strong>{objective.title}</strong>
                  <span>{objective.description || 'No description'}</span>
                </div>
                <span className={`agency-objective-status status-${objective.status}`}>{objectiveStatusLabel(objective)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
