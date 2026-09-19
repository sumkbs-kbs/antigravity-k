/**
 * CR-14 F-12 — 번들 provenance 핀(커밋된 기록)이 실제로 읽히는지 확인한다.
 *
 * 이 테스트가 없으면 핀 파일이 이름만 남고 `buildId` 는 다시 git HEAD 를 따라가도 아무도
 * 모른다 — 그러면 커밋마다 `dashboard-build` 가 후보 트리를 흔들어(자산 22개 교체 실측)
 * 커밋된 후보에서 단일 지문 20/20 을 완주할 수 없게 된다.
 */
import { describe, expect, it } from 'vitest';

import { BUILD_PROVENANCE_FILE, readBuildProvenancePin } from '../../buildStamp';

describe('번들 provenance 핀 (CR-14 F-12)', () => {
  it('파일 이름이 계약이다', () => {
    expect(BUILD_PROVENANCE_FILE).toBe('build-provenance.json');
  });

  it('커밋된 핀에서 실제 소스 리비전을 읽는다', () => {
    const pin = readBuildProvenancePin();
    expect(pin.buildId).toMatch(/^[0-9a-f]{7,40}$/);
  });

  it('빌드 시각은 미기록(null)을 허용한다 — 추측값으로 채우지 않는다', () => {
    const pin = readBuildProvenancePin();
    expect(pin.builtAt === null || typeof pin.builtAt === 'string').toBe(true);
  });
});
