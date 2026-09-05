import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ApprovalQueue } from './ApprovalQueue';
import { ApprovalRequestSchema } from './approvalApi';

vi.mock('../../components/Editor/DiffViewer', () => ({
  default: ({ change }: Readonly<{ change: Readonly<{ newContent: string }> }>) => (
    <pre data-testid="approval-diff">{change.newContent}</pre>
  ),
}));

const approval = ApprovalRequestSchema.parse({
  request_id: 'approval-1',
  tool_name: 'apply_patch',
  risk_level: 'high',
  description: '설정 파일 수정',
  diff_preview: '--- a/settings.ts\n+++ b/settings.ts\n@@ -1 +1 @@\n-old\n+new',
  status: 'pending',
  created_at: 1_777_000_000,
  timeout_sec: 120,
  auto_review: {
    decision: 'escalate',
    risk_score: 0.8,
    reason_codes: ['file_change'],
    rationale: '사용자 확인이 필요합니다.',
    reviewer: 'policy-v1',
    reviewed_at: 1_777_000_001,
  },
});

describe('ApprovalQueue', () => {
  it('renders the server approval diff and sends explicit decisions', () => {
    const onResolve = vi.fn();
    render(
      <ApprovalQueue
        approvals={[approval]}
        pendingRequestId={null}
        error={null}
        onResolve={onResolve}
      />,
    );

    expect(screen.getByRole('heading', { name: '승인 대기열' })).toBeInTheDocument();
    expect(screen.getByTestId('approval-diff')).toHaveTextContent('new');
    expect(screen.getByText('자동 검토 · 사용자 확인 필요')).toBeInTheDocument();
    expect(screen.getByText('80% 위험도')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '설정 파일 수정 승인' }));
    expect(onResolve).toHaveBeenCalledWith('approval-1', 'approve');
    fireEvent.click(screen.getByRole('button', { name: '설정 파일 수정 거절' }));
    expect(onResolve).toHaveBeenCalledWith('approval-1', 'deny');
  });
});
