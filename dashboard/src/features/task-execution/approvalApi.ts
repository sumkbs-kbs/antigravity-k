import ky from 'ky';
import { z } from 'zod';

export const ApprovalDecisionSchema = z.enum(['approve', 'deny', 'always_allow']);
export const ApprovalRequestSchema = z.object({
  request_id: z.string().min(1),
  tool_name: z.string().min(1),
  risk_level: z.string().min(1),
  description: z.string(),
  diff_preview: z.string(),
  status: z.literal('pending'),
  created_at: z.number().nonnegative(),
  timeout_sec: z.number().int().positive(),
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
export type ApprovalRequest = z.infer<typeof ApprovalRequestSchema>;

function accessHeaders(): Headers {
  const headers = new Headers({ Accept: 'application/json' });
  const pin = localStorage.getItem('ag_access_pin');
  if (pin !== null && pin.length > 0) headers.set('X-Access-Pin', pin);
  return headers;
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
