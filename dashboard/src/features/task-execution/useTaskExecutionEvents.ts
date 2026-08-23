import { useCallback, useEffect, useState } from 'react';

import {
  cancelTask,
  fetchTaskEvents,
  fetchTaskList,
  forkTask,
  resumeTask,
  streamTaskEvents,
  submitTask,
} from './taskExecutionApi';
import type { PendingTaskAction } from './TaskQueuePanel';
import type { TaskEvent, TaskId, TaskSummary } from './taskExecutionSchema';

export type TaskConnectionState = 'idle' | 'loading' | 'connected' | 'reconnecting' | 'complete' | 'error';

export type TaskExecutionState = Readonly<{
  tasks: readonly TaskSummary[];
  selectedTaskId: TaskId | null;
  events: readonly TaskEvent[];
  connectionState: TaskConnectionState;
  error: string | null;
  pendingAction: PendingTaskAction | null;
  selectTask: (taskId: TaskId) => void;
  submit: (prompt: string) => void;
  cancel: (taskId: TaskId) => void;
  resume: (taskId: TaskId) => void;
  fork: (taskId: TaskId) => void;
  retry: () => void;
}>;

function mergeEvents(current: readonly TaskEvent[], incoming: readonly TaskEvent[]): readonly TaskEvent[] {
  const bySequence = new Map<number, TaskEvent>();
  for (const event of current) bySequence.set(event.sequence, event);
  for (const event of incoming) bySequence.set(event.sequence, event);
  return [...bySequence.values()].sort((left, right) => left.sequence - right.sequence);
}

function waitForReconnect(): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, 1_000));
}

export function useTaskExecutionEvents(): TaskExecutionState {
  const [tasks, setTasks] = useState<readonly TaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<TaskId | null>(null);
  const [events, setEvents] = useState<readonly TaskEvent[]>([]);
  const [connectionState, setConnectionState] = useState<TaskConnectionState>('loading');
  const [error, setError] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [pendingAction, setPendingAction] = useState<PendingTaskAction | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setConnectionState('loading');
    setError(null);

    void fetchTaskList(controller.signal)
      .then((nextTasks) => {
        if (controller.signal.aborted) return;
        setTasks(nextTasks);
        setSelectedTaskId((current) => {
          if (current !== null && nextTasks.some((task) => task.task_id === current)) return current;
          return nextTasks[0]?.task_id ?? null;
        });
        if (nextTasks.length === 0) setConnectionState('idle');
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (!(caught instanceof Error)) throw caught;
        setError(caught.message);
        setConnectionState('error');
      });

    return () => controller.abort();
  }, [reloadVersion]);

  useEffect(() => {
    if (selectedTaskId === null) {
      setEvents([]);
      return;
    }

    const controller = new AbortController();
    setEvents([]);
    setError(null);
    setConnectionState('loading');

    const run = async (): Promise<void> => {
      const replay = await fetchTaskEvents(selectedTaskId, 0, controller.signal);
      if (controller.signal.aborted) return;
      let sequence = replay.lastSequence;
      setEvents(replay.events);
      setConnectionState('connected');

      for (let attempt = 0; attempt < 3 && !controller.signal.aborted; attempt += 1) {
        try {
          const end = await streamTaskEvents(selectedTaskId, sequence, controller.signal, {
            onEvent: (event) => {
              sequence = Math.max(sequence, event.sequence);
              setEvents((current) => mergeEvents(current, [event]));
              setConnectionState('connected');
            },
          });
          if (controller.signal.aborted) return;
          setConnectionState('complete');
          sequence = Math.max(sequence, end.lastSequence);
          return;
        } catch (caught: unknown) {
          if (controller.signal.aborted) return;
          if (!(caught instanceof Error)) throw caught;
          if (attempt === 2) {
            setError(caught.message);
            setConnectionState('error');
            return;
          }
          setConnectionState('reconnecting');
          await waitForReconnect();
          const missed = await fetchTaskEvents(selectedTaskId, sequence, controller.signal);
          sequence = missed.lastSequence;
          setEvents((current) => mergeEvents(current, missed.events));
        }
      }
    };

    void run().catch((caught: unknown) => {
      if (controller.signal.aborted) return;
      if (!(caught instanceof Error)) throw caught;
      setError(caught.message);
      setConnectionState('error');
    });

    return () => controller.abort();
  }, [selectedTaskId, reloadVersion]);

  const selectTask = useCallback((taskId: TaskId) => setSelectedTaskId(taskId), []);
  const retry = useCallback(() => setReloadVersion((current) => current + 1), []);

  const submit = useCallback((prompt: string): void => {
    setPendingAction({ kind: 'submit' });
    setError(null);
    void submitTask(prompt)
      .then((taskId) => {
        setSelectedTaskId(taskId);
        setReloadVersion((current) => current + 1);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof Error)) throw caught;
        setError(caught.message);
      })
      .finally(() => setPendingAction(null));
  }, []);

  const cancel = useCallback((taskId: TaskId): void => {
    setPendingAction({ kind: 'cancel', taskId });
    setError(null);
    void cancelTask(taskId)
      .then(() => setReloadVersion((current) => current + 1))
      .catch((caught: unknown) => {
        if (!(caught instanceof Error)) throw caught;
        setError(caught.message);
      })
      .finally(() => setPendingAction(null));
  }, []);

  const resume = useCallback((taskId: TaskId): void => {
    setPendingAction({ kind: 'resume', taskId });
    setError(null);
    void resumeTask(taskId)
      .then(() => setReloadVersion((current) => current + 1))
      .catch((caught: unknown) => {
        if (!(caught instanceof Error)) throw caught;
        setError(caught.message);
      })
      .finally(() => setPendingAction(null));
  }, []);

  const fork = useCallback((taskId: TaskId): void => {
    setPendingAction({ kind: 'fork', taskId });
    setError(null);
    void forkTask(taskId)
      .then((forkedTaskId) => {
        setSelectedTaskId(forkedTaskId);
        setReloadVersion((current) => current + 1);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof Error)) throw caught;
        setError(caught.message);
      })
      .finally(() => setPendingAction(null));
  }, []);

  return {
    tasks,
    selectedTaskId,
    events,
    connectionState,
    error,
    pendingAction,
    selectTask,
    submit,
    cancel,
    resume,
    fork,
    retry,
  };
}
