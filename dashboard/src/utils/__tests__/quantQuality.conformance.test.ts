/**
 * quantQuality conformance fixture 테스트 (Phase 46)
 * =====================================================
 * tests/fixtures/quant_quality_conformance.json 하나를 Python(engine/quant_quality.py)과
 * 공유 검증한다 — 어느 한쪽 구현이 어긋나면 동일 케이스 셋에서 함께 실패해 드리프트를 막는다.
 *
 * 대응 테스트: tests/test_quant_quality.py (같은 fixture를 소비하는 Python 쪽 쌍생 테스트)
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { quantQuality } from '../quantQuality';

interface Fixture {
  version: number;
  token_cases: { token: string; level: string }[];
  grade_order: string[];
  grade_meta: Record<string, { grade: string; label: string }>;
}

const fixturePath = join(__dirname, '..', '..', '..', '..', 'tests', 'fixtures', 'quant_quality_conformance.json');
const fixture: Fixture = JSON.parse(readFileSync(fixturePath, 'utf-8'));

describe('quantQuality conformance fixture (shared with Python)', () => {
  it('fixture is well-formed', () => {
    expect(fixture.version).toBe(1);
    expect(fixture.token_cases.length).toBeGreaterThanOrEqual(30);
    expect(fixture.grade_order).toEqual(['unknown', 'compact', 'balanced', 'high', 'premium']);
    expect(Object.keys(fixture.grade_meta).sort()).toEqual([...fixture.grade_order].sort());
  });

  it('every token case matches the shared expectation', () => {
    for (const { token, level } of fixture.token_cases) {
      expect(quantQuality(token).level, `token=${JSON.stringify(token)}`).toBe(level);
    }
  });

  it('grade letters and labels match grade_meta', () => {
    const representativeToken: Record<string, string> = {
      premium: 'Q8_0',
      high: 'Q6_K',
      balanced: 'Q4_K_M',
      compact: 'Q2_K',
      unknown: '',
    };
    for (const [level, meta] of Object.entries(fixture.grade_meta)) {
      const info = quantQuality(representativeToken[level] ?? '');
      expect(info.level).toBe(level);
      expect(info.grade).toBe(meta.grade);
      expect(info.label).toBe(meta.label);
    }
  });
});
