import { useCallback, useEffect, useState } from 'react';

import {
  fetchPendingApprovals,
  resolveApproval,
  type ApprovalDecision,
  type ApprovalRequest,
} from './approvalApi';

export type ApprovalQueueState = Readonly<{
  approvals: readonly ApprovalRequest[];
  pendingRequestId: string | null;
  error: string | null;
  resolve: (requestId: string, decision: ApprovalDecision) => void;
}>;

export function useApprovalQueue(): ApprovalQueueState {
  const [approvals, setApprovals] = useState<readonly ApprovalRequest[]>([]);
  const [pendingRequestId, setPendingRequestId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const refresh = async (): Promise<void> => {
      try {
        const pending = await fetchPendingApprovals(controller.signal);
        if (!controller.signal.aborted) {
          setApprovals(pending);
          setError(null);
        }
      } catch (caught: unknown) {
        if (controller.signal.aborted) return;
        if (!(caught instanceof Error)) throw caught;
        setError(caught.message);
      }
    };
    void refresh();
    const interval = window.setInterval(() => void refresh(), 3_000);
    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, []);

  const resolve = useCallback((requestId: string, decision: ApprovalDecision): void => {
    setPendingRequestId(requestId);
    setError(null);
    void resolveApproval(requestId, decision)
      .then(() => setApprovals((current) => current.filter((item) => item.request_id !== requestId)))
      .catch((caught: unknown) => {
        if (!(caught instanceof Error)) throw caught;
        setError(caught.message);
      })
      .finally(() => setPendingRequestId(null));
  }, []);

  return { approvals, pendingRequestId, error, resolve };
}
