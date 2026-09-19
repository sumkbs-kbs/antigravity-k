import { z } from 'zod';

export const GitFileSchema = z.object({
  x: z.string(),
  y: z.string(),
  staged_status: z.string(),
  unstaged_status: z.string(),
  file_path: z.string(),
  old_path: z.string().nullable().optional(),
  is_renamed: z.boolean().optional(),
});

export const GitCommitSchema = z.object({
  hash: z.string(),
  short_hash: z.string(),
  author_name: z.string(),
  author_email: z.string(),
  date: z.string(),
  message: z.string(),
  refs: z.string().optional(),
});

export const GitBranchSchema = z.object({
  name: z.string(),
  is_current: z.boolean(),
  is_remote: z.boolean(),
  upstream: z.string().nullable().optional(),
});

export const GitStashSchema = z.object({
  short_hash: z.string(),
  date: z.string(),
  message: z.string(),
});

export const GitGraphNodeSchema = z.object({
  graph: z.string(),
  hash: z.string(),
  short_hash: z.string(),
  author: z.string(),
  message: z.string(),
  date: z.string(),
  refs: z.string(),
});

const GitFailureSchema = z.object({
  ok: z.literal(false),
  error: z.string().min(1).optional(),
});

const GitStatusSuccessSchema = z.object({
  ok: z.literal(true),
  branch: z.string(),
  upstream: z.string().nullable(),
  ahead: z.number().int().nonnegative(),
  behind: z.number().int().nonnegative(),
  files: z.array(GitFileSchema),
  counts: z.object({
    staged: z.number().int().nonnegative(),
    unstaged: z.number().int().nonnegative(),
    untracked: z.number().int().nonnegative(),
    total: z.number().int().nonnegative(),
  }),
});

const GitLogSuccessSchema = z.object({
  ok: z.literal(true),
  commits: z.array(GitCommitSchema),
  count: z.number().int().nonnegative().optional(),
});

const GitBranchesSuccessSchema = z.object({
  ok: z.literal(true),
  branches: z.array(GitBranchSchema),
  current: z.string(),
});

const GitDiffSuccessSchema = z.object({
  ok: z.literal(true),
  diff: z.string(),
  stat: z.string(),
  staged: z.boolean().optional(),
  file: z.string().optional(),
});

const GitGraphSuccessSchema = z.object({
  ok: z.literal(true),
  nodes: z.array(GitGraphNodeSchema),
  count: z.number().int().nonnegative().optional(),
});

export const GitStatusResponseSchema = z.discriminatedUnion('ok', [GitStatusSuccessSchema, GitFailureSchema]);
export const GitLogResponseSchema = z.discriminatedUnion('ok', [GitLogSuccessSchema, GitFailureSchema]);
export const GitBranchesResponseSchema = z.discriminatedUnion('ok', [GitBranchesSuccessSchema, GitFailureSchema]);
export const GitDiffResponseSchema = z.discriminatedUnion('ok', [GitDiffSuccessSchema, GitFailureSchema]);
export const GitGraphResponseSchema = z.discriminatedUnion('ok', [GitGraphSuccessSchema, GitFailureSchema]);
export const GitMutationResponseSchema = z.object({ ok: z.boolean() });

export type GitFile = z.infer<typeof GitFileSchema>;
export type GitCommit = z.infer<typeof GitCommitSchema>;
export type GitBranch = z.infer<typeof GitBranchSchema>;
export type GitStash = z.infer<typeof GitStashSchema>;
export type GitGraphNode = z.infer<typeof GitGraphNodeSchema>;
export type GitStatusResponse = z.infer<typeof GitStatusResponseSchema>;
export type GitLogResponse = z.infer<typeof GitLogResponseSchema>;
export type GitBranchesResponse = z.infer<typeof GitBranchesResponseSchema>;
export type GitDiffResponse = z.infer<typeof GitDiffResponseSchema>;
export type GitGraphResponse = z.infer<typeof GitGraphResponseSchema>;
