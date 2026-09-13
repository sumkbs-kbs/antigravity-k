/**
 * uiBuildInfo · CR-10
 * ====================
 * 빌드 시 `define`으로 주입된 값이 그대로 노출되는지, 그리고 미기록 값이
 * 추측값이 아니라 `null`인지 고정한다.
 */

import { describe, expect, it } from 'vitest';

import { getUiBuildInfo } from './uiBuildInfo';

describe('getUiBuildInfo (CR-10)', () => {
  it('주입된 번들 버전을 반환한다', () => {
    const info = getUiBuildInfo();
    expect(info.version).toBe('0.1.0');
  });

  it('빌드 식별자는 문자열이거나 null이다 — 빈 문자열로 위장하지 않는다', () => {
    const info = getUiBuildInfo();
    expect(info.buildId === null || info.buildId.length > 0).toBe(true);
    expect(info.builtAt === null || info.builtAt.length > 0).toBe(true);
  });
});
