import { useCallback, useEffect, useRef, useState } from 'react';

import {
  cancelTask,
  fetchTaskEvents,
  fetchTaskList,
  forkTask,
  resumeTask,
  streamTaskEvents,
  submitTask,
} from './taskExecutionApi';
import {
  compactTaskEventReplica,
  createTaskEventReplica,
  mergeTaskEventReplica,
  readTaskEventReplicaCache,
  replaceTaskEventReplica,
  writeTaskEventReplicaCache,
  type TaskEventReplicaState,
} from './taskEventReplica';
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
  const replicaRef = useRef<TaskEventReplicaState | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const resetTimer = window.setTimeout(() => {
      setConnectionState('loading');
      setError(null);
    }, 0);

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

    return () => {
      window.clearTimeout(resetTimer);
      controller.abort();
    };
  }, [reloadVersion]);

  useEffect(() => {
    if (selectedTaskId === null) {
      replicaRef.current = null;
      const clearTimer = window.setTimeout(() => setEvents([]), 0);
      return () => window.clearTimeout(clearTimer);
    }

    const controller = new AbortController();
    const cachedReplica = readTaskEventReplicaCache(selectedTaskId);
    let replica = cachedReplica ?? createTaskEventReplica(selectedTaskId);
    replicaRef.current = replica;
    const resetTimer = window.setTimeout(() => {
      setEvents(replica.events);
      setError(null);
      setConnectionState('loading');
    }, 0);

    const run = async (): Promise<void> => {
      const replayCursor = cachedReplica?.contiguousSequence ?? 0;
      const replay = await fetchTaskEvents(selectedTaskId, replayCursor, controller.signal);
      if (controller.signal.aborted) return;
      replica = cachedReplica === null
        ? replaceTaskEventReplica(selectedTaskId, replay.events, replay.lastSequence)
        : mergeTaskEventReplica(replica, replay.events, replay.lastSequence);
      replica = compactTaskEventReplica(replica);
      replicaRef.current = replica;
      writeTaskEventReplicaCache(replica);
      let sequence = replica.contiguousSequence;
      setEvents(replica.events);
      setConnectionState('connected');
      let gapRecovery: Promise<void> | null = null;

      const recoverGap = async (afterSequence: number): Promise<void> => {
        const missed = await fetchTaskEvents(selectedTaskId, afterSequence, controller.signal);
        if (controller.signal.aborted) return;
        replica = compactTaskEventReplica(mergeTaskEventReplica(replica, missed.events, missed.lastSequence));
        replicaRef.current = replica;
        sequence = replica.contiguousSequence;
        writeTaskEventReplicaCache(replica);
        setEvents(replica.events);
        setConnectionState(replica.gap === null ? 'connected' : 'reconnecting');
      };

      for (let attempt = 0; attempt < 3 && !controller.signal.aborted; attempt += 1) {
        try {
          const end = await streamTaskEvents(selectedTaskId, sequence, controller.signal, {
            onEvent: (event) => {
              const next = compactTaskEventReplica(mergeTaskEventReplica(replica, [event]));
              replica = next;
              replicaRef.current = next;
              sequence = next.contiguousSequence;
              writeTaskEventReplicaCache(next);
              setEvents(next.events);
              setConnectionState(next.gap === null ? 'connected' : 'reconnecting');
              if (next.gap !== null && gapRecovery === null) {
                gapRecovery = recoverGap(next.contiguousSequence).finally(() => {
                  gapRecovery = null;
                });
              }
            },
          });
          if (controller.signal.aborted) return;
          const pendingGapRecovery = gapRecovery;
          if (pendingGapRecovery !== null) await pendingGapRecovery;
          if (end.lastSequence > replica.contiguousSequence) {
            setConnectionState('reconnecting');
            await recoverGap(replica.contiguousSequence);
          }
          if (replica.gap !== null || replica.contiguousSequence < end.lastSequence) {
            setError(`Task event replay is incomplete at sequence ${replica.contiguousSequence}.`);
            setConnectionState('error');
            return;
          }
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
          await recoverGap(sequence);
        }
      }
    };

    void run().catch((caught: unknown) => {
      if (controller.signal.aborted) return;
      if (!(caught instanceof Error)) throw caught;
      setError(caught.message);
      setConnectionState('error');
    });

    return () => {
      window.clearTimeout(resetTimer);
      controller.abort();
    };
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
