import ky from 'ky';
import { z } from 'zod';

import { createAccessPinHeaders } from '../../utils/accessPinCredential';

export const ApprovalDecisionSchema = z.enum(['approve', 'deny', 'always_allow']);
export const ApprovalReviewSchema = z.object({
  decision: z.enum(['approve', 'deny', 'escalate']),
  risk_score: z.number().min(0).max(1),
  reason_codes: z.array(z.string()).readonly(),
  rationale: z.string(),
  reviewer: z.string().min(1),
  reviewed_at: z.number().nonnegative(),
}).readonly();
export const ApprovalRequestSchema = z.object({
  request_id: z.string().min(1),
  tool_name: z.string().min(1),
  risk_level: z.string().min(1),
  description: z.string(),
  diff_preview: z.string(),
  status: z.literal('pending'),
  created_at: z.number().nonnegative(),
  timeout_sec: z.number().int().positive(),
  auto_review: ApprovalReviewSchema.nullable(),
}).readonly();

const ApprovalListResponseSchema = z.object({
  pending: z.array(ApprovalRequestSchema).readonly(),
  count: z.number().int().nonnegative(),
}).readonly();

const ApprovalResolveResponseSchema = z.object({
  ok: z.literal(true),
  request_id: z.string().min(1),
  status: z.string().min(1),
}).readonly();

export type ApprovalDecision = z.infer<typeof ApprovalDecisionSchema>;
export type ApprovalReview = z.infer<typeof ApprovalReviewSchema>;
export type ApprovalRequest = z.infer<typeof ApprovalRequestSchema>;

function accessHeaders(): Headers {
  return createAccessPinHeaders({ Accept: 'application/json' });
}

export async function fetchPendingApprovals(signal: AbortSignal): Promise<readonly ApprovalRequest[]> {
  const raw: unknown = await ky.get('/api/approval/pending', {
    headers: accessHeaders(),
    signal,
    retry: 1,
    timeout: 10_000,
  }).json();
  return ApprovalListResponseSchema.parse(raw).pending;
}

export async function resolveApproval(requestId: string, decision: ApprovalDecision): Promise<void> {
  const raw: unknown = await ky.post(`/api/approval/${encodeURIComponent(requestId)}/resolve`, {
    headers: accessHeaders(),
    json: { decision },
    retry: 0,
    timeout: 10_000,
  }).json();
  ApprovalResolveResponseSchema.parse(raw);
}
