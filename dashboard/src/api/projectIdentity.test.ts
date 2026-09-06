import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useProjectStore } from '../stores/projectStore';
import {
  createProjectIdentityHeaders,
  withProjectIdentityPayload,
} from './projectIdentity';
import { streamChatCompletion } from './client';

describe('WS-04 request identity sync', () => {
  beforeEach(() => {
    useProjectStore.setState({
      projects: [],
      activeProjectId: 'proj_label',
      activeProjectName: 'LabelProj',
      activeProjectPath: '/tmp/label',
      projectRevision: 5,
      switchEpoch: 3,
      isSwitching: false,
      lastSwitchError: null,
      hydrated: true,
    });
    sessionStorage.clear();
  });

  it('streamChatCompletion body includes project_id matching store label', async () => {
    let capturedBody: Record<string, unknown> | null = null;
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
      capturedBody = JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>;
      const headers = new Headers(init?.headers);
      expect(headers.get('X-AGK-Project-Id')).toBe('proj_label');
      expect(headers.get('X-AGK-Project-Revision')).toBe('5');
      return {
        ok: true,
        body: {
          getReader: () => ({
            read: async () => ({ done: true, value: undefined }),
          }),
        },
      };
    }));

    await streamChatCompletion(
      { model: 'm', messages: [], stream: true },
      { onChunk: () => {}, onDone: () => {}, onError: () => {} },
    );

    expect(capturedBody).not.toBeNull();
    const body = capturedBody as unknown as Record<string, unknown>;
    expect(body.project_id).toBe('proj_label');
    expect(body.project_revision).toBe(5);
    // Label (store) and payload must match.
    expect(useProjectStore.getState().activeProjectName).toBe('LabelProj');
    expect(body.project_id).toBe(useProjectStore.getState().activeProjectId);
  });

  it('does not overwrite explicit project_id in payload', () => {
    const payload = withProjectIdentityPayload({ project_id: 'explicit', model: 'x' });
    expect(payload.project_id).toBe('explicit');
    expect(payload.project_revision).toBe(5);
  });

  it('headers carry session + project identity', () => {
    const headers = createProjectIdentityHeaders();
    expect(headers.get('X-AGK-Session-Id')).toBeTruthy();
    expect(headers.get('X-AGK-Project-Id')).toBe('proj_label');
  });
});
