/**
 * Client session id for X-AGK-Session-Id (WS-01 / WS-04).
 * Kept separate from projectIdentity to avoid circular imports with projectStore.
 */

export const SESSION_ID_HEADER = 'X-AGK-Session-Id';
export const CLIENT_SESSION_STORAGE_KEY = 'agk_client_session_id';

function randomId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

/** Stable per-tab session id for X-AGK-Session-Id (server binding revisions). */
export function getOrCreateClientSessionId(): string {
  if (typeof window === 'undefined') return 'default';
  try {
    const existing = window.sessionStorage.getItem(CLIENT_SESSION_STORAGE_KEY)?.trim();
    if (existing) return existing;
    const next = randomId('sess');
    window.sessionStorage.setItem(CLIENT_SESSION_STORAGE_KEY, next);
    return next;
  } catch {
    return 'default';
  }
}
