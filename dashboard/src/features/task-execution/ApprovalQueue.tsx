import { useMemo, useState } from 'react';

import DiffViewer from '../../components/Editor/DiffViewer';
import type { ProposedChange } from '../../stores/changeStore';
import type { ApprovalDecision, ApprovalRequest, ApprovalReview } from './approvalApi';

type ApprovalQueueProps = Readonly<{
  approvals: readonly ApprovalRequest[];
  pendingRequestId: string | null;
  error: string | null;
  onResolve: (requestId: string, decision: ApprovalDecision) => void;
}>;

function diffPath(lines: readonly string[]): string {
  const header = lines.find((line) => line.startsWith('+++ '));
  if (header === undefined) return 'proposed-change.diff';
  return header.slice(4).replace(/^b\//, '').replace(/ \(after\)$/, '') || 'proposed-change.diff';
}

function reviewLabel(review: ApprovalReview): string {
  if (review.decision === 'approve') return '승인 후보';
  if (review.decision === 'deny') return '거부 권고';
  return '사용자 확인 필요';
}

export function approvalDiffChange(approval: ApprovalRequest): ProposedChange {
  const lines = approval.diff_preview.split('\n');
  const original: string[] = [];
  const modified: string[] = [];
  let additions = 0;
  let deletions = 0;

  for (const line of lines) {
    if (line.startsWith('--- ') || line.startsWith('+++ ') || line.startsWith('@@')) continue;
    if (line.startsWith('-')) {
      original.push(line.slice(1));
      deletions += 1;
    } else if (line.startsWith('+')) {
      modified.push(line.slice(1));
      additions += 1;
    } else {
      const content = line.startsWith(' ') ? line.slice(1) : line;
      original.push(content);
      modified.push(content);
    }
  }

  const filePath = diffPath(lines);
  return {
    id: approval.request_id,
    filePath,
    fileName: filePath.split('/').at(-1) ?? filePath,
    originalContent: original.join('\n'),
    newContent: modified.join('\n'),
    status: 'pending',
    diffStats: { additions, deletions },
    createdAt: approval.created_at * 1_000,
    description: approval.description,
  };
}

export function ApprovalQueue({ approvals, pendingRequestId, error, onResolve }: ApprovalQueueProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = approvals.find((approval) => approval.request_id === selectedId) ?? approvals[0] ?? null;
  const change = useMemo(() => selected === null ? null : approvalDiffChange(selected), [selected]);

  return (
    <section className="approval-queue" aria-labelledby="approval-queue-title">
      <header>
        <div>
          <h4 id="approval-queue-title">승인 대기열</h4>
          <span>{approvals.length}건 대기</span>
        </div>
      </header>
      {error !== null && <p className="approval-queue-error" role="alert">{error}</p>}
      {approvals.length === 0 ? (
        <p className="approval-queue-empty">대기 중인 승인 요청이 없습니다.</p>
      ) : (
        <div className="approval-queue-layout">
          <ul className="approval-queue-list">
            {approvals.map((approval) => (
              <li key={approval.request_id}>
                <button
                  type="button"
                  className={approval.request_id === selected?.request_id ? 'is-selected' : undefined}
                  onClick={() => setSelectedId(approval.request_id)}
                >
                  <strong>{approval.description}</strong>
                  <span>{approval.tool_name} · {approval.risk_level}</span>
                </button>
              </li>
            ))}
          </ul>
          {selected !== null && change !== null && (
            <div className="approval-queue-detail">
              {selected.diff_preview.length > 0 ? (
                <DiffViewer change={change} showActions={false} height={280} />
              ) : (
                <p className="approval-queue-empty">이 요청에는 파일 변경 미리보기가 없습니다.</p>
              )}
              {selected.auto_review !== null && (
                <aside className={`approval-review approval-review-${selected.auto_review.decision}`} aria-label="자동 검토 결과">
                  <div className="approval-review-heading">
                    <strong>자동 검토 · {reviewLabel(selected.auto_review)}</strong>
                    <span>{Math.round(selected.auto_review.risk_score * 100)}% 위험도</span>
                  </div>
                  <p>{selected.auto_review.rationale}</p>
                  <small>{selected.auto_review.reviewer} · 사용자 결정은 별도로 필요합니다.</small>
                </aside>
              )}
              <div className="approval-queue-actions">
                <button
                  type="button"
                  disabled={pendingRequestId === selected.request_id}
                  onClick={() => onResolve(selected.request_id, 'deny')}
                  aria-label={`${selected.description} 거절`}
                >
                  거절
                </button>
                <button
                  type="button"
                  disabled={pendingRequestId === selected.request_id}
                  onClick={() => onResolve(selected.request_id, 'always_allow')}
                  aria-label={`${selected.description} 항상 허용`}
                >
                  항상 허용
                </button>
                <button
                  type="button"
                  className="is-primary"
                  disabled={pendingRequestId === selected.request_id}
                  onClick={() => onResolve(selected.request_id, 'approve')}
                  aria-label={`${selected.description} 승인`}
                >
                  승인
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
