import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useProjectStore } from '../projectStore';
import {
  PROJECT_ID_HEADER,
  PROJECT_REVISION_HEADER,
  SESSION_ID_HEADER,
  createProjectIdentityHeaders,
  isIdentityCurrent,
  withProjectIdentityPayload,
  withProjectIdentitySearchParams,
} from '../../api/projectIdentity';

describe('projectStore (WS-04)', () => {
  beforeEach(() => {
    useProjectStore.setState({
      projects: [],
      activeProjectId: null,
      activeProjectName: 'Ssak-Ai',
      activeProjectPath: '/',
      projectRevision: null,
      switchEpoch: 0,
      isSwitching: false,
      lastSwitchError: null,
      hydrated: false,
    });
    vi.restoreAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('applyActiveProject is the single source and bumps switchEpoch + revision', () => {
    useProjectStore.getState().applyActiveProject(
      { id: 'proj_a', name: 'Alpha', path: '/tmp/alpha' },
      3,
    );
    const s = useProjectStore.getState();
    expect(s.activeProjectId).toBe('proj_a');
    expect(s.activeProjectName).toBe('Alpha');
    expect(s.activeProjectPath).toBe('/tmp/alpha');
    expect(s.projectRevision).toBe(3);
    expect(s.switchEpoch).toBe(1);
    expect(localStorage.getItem('agk_active_project')).toBe('/tmp/alpha');
    expect(localStorage.getItem('agk_active_project_id')).toBe('proj_a');
  });

  it('switchToProject posts project_id and applies session revision from response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        project: { id: 'proj_b', name: 'Beta', path: '/tmp/beta', is_active: true, tasks: [] },
        session_active_project: {
          session_id: 'sess_test',
          project_id: 'proj_b',
          revision: 7,
          bound_at: '2026-09-06T00:00:00Z',
        },
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await useProjectStore.getState().switchToProject({
      id: 'proj_b',
      name: 'Beta',
      path: '/tmp/beta',
      is_active: false,
      tasks: [],
    });

    expect(result.ok).toBe(true);
    expect(result.revision).toBe(7);
    expect(useProjectStore.getState().activeProjectId).toBe('proj_b');
    expect(useProjectStore.getState().projectRevision).toBe(7);
    expect(useProjectStore.getState().switchEpoch).toBe(1);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/projects/switch');
    expect(JSON.parse(String(init.body))).toEqual({ project_id: 'proj_b' });
    const headers = new Headers(init.headers);
    expect(headers.get(SESSION_ID_HEADER)).toBeTruthy();
  });

  it('identity helpers attach project_id + revision to payload/headers/query', () => {
    useProjectStore.getState().applyActiveProject(
      { id: 'proj_c', name: 'Gamma', path: '/tmp/gamma' },
      2,
    );
    const payload = withProjectIdentityPayload({ model: 'local', messages: [] });
    expect(payload.project_id).toBe('proj_c');
    expect(payload.project_revision).toBe(2);

    const headers = createProjectIdentityHeaders({ 'Content-Type': 'application/json' });
    expect(headers.get(PROJECT_ID_HEADER)).toBe('proj_c');
    expect(headers.get(PROJECT_REVISION_HEADER)).toBe('2');
    expect(headers.get(SESSION_ID_HEADER)).toBeTruthy();

    const url = withProjectIdentitySearchParams('/api/fs/list?dir=.');
    expect(url).toContain('project_id=proj_c');
    expect(url).toContain('project_revision=2');
  });

  it('isIdentityCurrent rejects stale epochs after switch', () => {
    useProjectStore.getState().applyActiveProject(
      { id: 'proj_old', name: 'Old', path: '/tmp/old' },
      1,
    );
    const epoch = useProjectStore.getState().switchEpoch;
    expect(isIdentityCurrent(epoch)).toBe(true);
    useProjectStore.getState().applyActiveProject(
      { id: 'proj_new', name: 'New', path: '/tmp/new' },
      2,
    );
    expect(isIdentityCurrent(epoch)).toBe(false);
    expect(isIdentityCurrent(useProjectStore.getState().switchEpoch)).toBe(true);
  });
});
