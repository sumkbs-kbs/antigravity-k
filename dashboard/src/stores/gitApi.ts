import type { ZodType } from 'zod';
import { createAccessPinHeaders } from '../utils/accessPinCredential';

import {
  GitBranchesResponseSchema,
  GitDiffResponseSchema,
  GitGraphResponseSchema,
  GitLogResponseSchema,
  GitMutationResponseSchema,
  GitStatusResponseSchema,
  type GitBranchesResponse,
  type GitDiffResponse,
  type GitGraphResponse,
  type GitLogResponse,
  type GitStatusResponse,
} from './gitSchema';

type GitMutationResponse = Readonly<{ ok: boolean }>;

const JSON_HEADERS = { 'Content-Type': 'application/json' } as const;

async function requestJson<T>(
  url: string,
  label: string,
  schema: ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: createAccessPinHeaders(init?.headers),
  });
  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('agk:pin-required'));
    }
    let message = `HTTP ${response.status}: ${response.statusText}`;
    const errorPayload: unknown = await response.json().catch(() => null);
    if (errorPayload !== null && typeof errorPayload === 'object') {
      if ('error' in errorPayload && typeof errorPayload.error === 'string') {
        message = errorPayload.error;
      } else if ('detail' in errorPayload && typeof errorPayload.detail === 'string') {
        message = errorPayload.detail;
      }
    }
    throw new Error(message);
  }
  const raw: unknown = await response.json();
  const parsed = schema.safeParse(raw);
  if (!parsed.success) throw new Error(`Invalid Git ${label} response`);
  return parsed.data;
}

function postJson<T>(url: string, body: unknown, label: string, schema: ZodType<T>): Promise<T> {
  return requestJson(url, label, schema, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export function fetchGitStatus(path: string): Promise<GitStatusResponse> {
  return requestJson(
    `/api/git/status?path=${encodeURIComponent(path)}`,
    'status',
    GitStatusResponseSchema,
  );
}

export function fetchGitLog(path: string, count: number, branch: string): Promise<GitLogResponse> {
  return postJson('/api/git/log', { path, count, branch }, 'log', GitLogResponseSchema);
}

export function fetchGitBranches(path: string): Promise<GitBranchesResponse> {
  return requestJson(
    `/api/git/branches?path=${encodeURIComponent(path)}`,
    'branches',
    GitBranchesResponseSchema,
  );
}

export function fetchGitDiff(file: string, staged: boolean, path: string): Promise<GitDiffResponse> {
  return postJson('/api/git/diff', { path, file, staged }, 'diff', GitDiffResponseSchema);
}

export function fetchGitGraph(path: string, count: number): Promise<GitGraphResponse> {
  return requestJson(
    `/api/git/graph?path=${encodeURIComponent(path)}&count=${count}`,
    'graph',
    GitGraphResponseSchema,
  );
}

export function stageGitFiles(files: string[], path: string): Promise<GitMutationResponse> {
  return postJson(
    '/api/git/add',
    { path, files, all: files.length === 0 },
    'stage',
    GitMutationResponseSchema,
  );
}

export function unstageGitFiles(files: string[], path: string): Promise<GitMutationResponse> {
  return postJson('/api/git/unstage', { path, files }, 'unstage', GitMutationResponseSchema);
}

export function commitGit(message: string, stageAll: boolean, path: string): Promise<GitMutationResponse> {
  return postJson(
    '/api/git/commit',
    { path, message, stage_all: stageAll },
    'commit',
    GitMutationResponseSchema,
  );
}

export function checkoutGitBranch(name: string, path: string): Promise<GitMutationResponse> {
  return postJson('/api/git/checkout', { path, name }, 'checkout', GitMutationResponseSchema);
}

export function createGitBranch(name: string, from: string, path: string): Promise<GitMutationResponse> {
  return postJson('/api/git/branch/create', { path, name, from }, 'branch create', GitMutationResponseSchema);
}

export function deleteGitBranch(name: string, force: boolean, path: string): Promise<GitMutationResponse> {
  return postJson('/api/git/branch/delete', { path, name, force }, 'branch delete', GitMutationResponseSchema);
}
