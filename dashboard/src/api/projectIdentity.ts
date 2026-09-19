/**
 * Project / session identity helpers (WS-04)
 * ==========================================
 * Attach project_id (+ revision) and X-AGK-Session-Id to chat / task / file requests.
 */

import { createAccessPinHeaders } from '../utils/accessPinCredential';
import { useProjectStore } from '../stores/projectStore';
import { SESSION_ID_HEADER, getOrCreateClientSessionId } from './clientSession';

export { SESSION_ID_HEADER, getOrCreateClientSessionId, CLIENT_SESSION_STORAGE_KEY } from './clientSession';

export const PROJECT_ID_HEADER = 'X-AGK-Project-Id';
export const PROJECT_REVISION_HEADER = 'X-AGK-Project-Revision';

export type ProjectIdentitySnapshot = Readonly<{
  projectId: string | null;
  projectRevision: number | null;
  switchEpoch: number;
  sessionId: string;
  projectName: string;
  projectPath: string;
}>;

export function getProjectIdentitySnapshot(): ProjectIdentitySnapshot {
  const state = useProjectStore.getState();
  return {
    projectId: state.activeProjectId,
    projectRevision: state.projectRevision,
    switchEpoch: state.switchEpoch,
    sessionId: getOrCreateClientSessionId(),
    projectName: state.activeProjectName,
    projectPath: state.activeProjectPath,
  };
}

/** PIN + session + project identity headers for all dashboard API calls. */
export function createProjectIdentityHeaders(initial?: HeadersInit): Headers {
  const headers = createAccessPinHeaders(initial);
  const identity = getProjectIdentitySnapshot();
  headers.set(SESSION_ID_HEADER, identity.sessionId);
  if (identity.projectId) {
    headers.set(PROJECT_ID_HEADER, identity.projectId);
  }
  if (identity.projectRevision != null && identity.projectRevision >= 0) {
    headers.set(PROJECT_REVISION_HEADER, String(identity.projectRevision));
  }
  return headers;
}

/**
 * Merge project_id (+ project_revision when known) into a JSON body.
 * Does not overwrite an explicit project_id already set by the caller.
 */
export function withProjectIdentityPayload<T extends Record<string, unknown>>(
  payload: T,
  identity: ProjectIdentitySnapshot = getProjectIdentitySnapshot(),
): T & { project_id?: string; project_revision?: number } {
  const next: Record<string, unknown> = { ...payload };
  if (identity.projectId && (next.project_id == null || next.project_id === '')) {
    next.project_id = identity.projectId;
  }
  if (
    identity.projectRevision != null
    && identity.projectRevision >= 0
    && next.project_revision == null
  ) {
    next.project_revision = identity.projectRevision;
  }
  return next as T & { project_id?: string; project_revision?: number };
}

/** Append project_id / project_revision query params for GET file requests. */
export function withProjectIdentitySearchParams(
  url: string,
  identity: ProjectIdentitySnapshot = getProjectIdentitySnapshot(),
): string {
  if (!identity.projectId) return url;
  const u = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  if (!u.searchParams.has('project_id')) {
    u.searchParams.set('project_id', identity.projectId);
  }
  if (
    identity.projectRevision != null
    && identity.projectRevision >= 0
    && !u.searchParams.has('project_revision')
  ) {
    u.searchParams.set('project_revision', String(identity.projectRevision));
  }
  return `${u.pathname}${u.search}${u.hash}`;
}

export function isIdentityCurrent(capturedEpoch: number): boolean {
  return useProjectStore.getState().switchEpoch === capturedEpoch;
}
