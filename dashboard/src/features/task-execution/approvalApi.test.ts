import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.hoisted(() => vi.fn());
const postMock = vi.hoisted(() => vi.fn());

vi.mock('ky', () => ({
  default: {
    get: getMock,
    post: postMock,
  },
}));

import {
  AlwaysAllowGrantSchema,
  fetchAlwaysAllowedGrants,
  resetAlwaysAllowed,
} from './approvalApi';

function jsonResponse(body: unknown): Readonly<{ json: () => Promise<unknown> }> {
  return { json: () => Promise.resolve(body) };
}

const grant = {
  tool_name: 'run_bash_command',
  granted_at: 1_777_000_000,
  granted_for: 'run_bash_command 실행',
  auto_approved_count: 2,
  last_auto_approved_at: 1_777_000_100,
};

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
});

describe('approvalApi always-allowed surface (F-33)', () => {
  it('reads the standing grants from the dedicated endpoint', async () => {
    // `/{request_id}` 가 아니라 전용 경로를 읽는다 — 서버에서 경로 순서가 뒤집히면 404 가 된다.
    getMock.mockReturnValue(jsonResponse({ grants: [grant], count: 1 }));

    const grants = await fetchAlwaysAllowedGrants(new AbortController().signal);

    expect(getMock).toHaveBeenCalledTimes(1);
    expect(String(getMock.mock.calls[0]?.[0])).toBe('/api/approval/always-allowed');
    expect(grants).toHaveLength(1);
    expect(grants[0]?.tool_name).toBe('run_bash_command');
    expect(grants[0]?.auto_approved_count).toBe(2);
  });

  it('reports how many grants the reset revoked', async () => {
    postMock.mockReturnValue(
      jsonResponse({ ok: true, revoked: ['run_bash_command'], message: "'항상 허용' 목록이 초기화되었습니다 (1건)" }),
    );

    const revoked = await resetAlwaysAllowed();

    expect(String(postMock.mock.calls[0]?.[0])).toBe('/api/approval/reset-always-allowed');
    expect(revoked).toEqual(['run_bash_command']);
  });

  it('rejects a grant payload without a reason or count', () => {
    // 근거와 횟수는 감사 표면이다 — 없으면 조용히 0으로 채우지 않고 계약 위반으로 실패한다.
    expect(() => AlwaysAllowGrantSchema.parse({ tool_name: 'write_file', granted_at: 1 })).toThrow();
    expect(() =>
      AlwaysAllowGrantSchema.parse({ ...grant, auto_approved_count: -1 }),
    ).toThrow();
  });
});
