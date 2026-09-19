/**
 * quantQuality 단위 테스트 — 양자화 품질 등급 산출 검증.
 * Phase 2 백엔드 파서(_QUANT_TOKEN_RE)가 추출하는 토큰과 동일한 입력 집합 사용.
 */

import { describe, expect, it } from 'vitest';
import { quantQuality } from './quantQuality';

describe('quantQuality', () => {
  it('assigns premium to near-lossless quants', () => {
    expect(quantQuality('Q8_0').level).toBe('premium');
    expect(quantQuality('UD-Q8_K_XL').level).toBe('premium');
    expect(quantQuality('F16').level).toBe('premium');
    expect(quantQuality('8bit').level).toBe('premium');
  });

  it('assigns high to Q6/Q5 K-quants', () => {
    expect(quantQuality('Q6_K').level).toBe('high');
    expect(quantQuality('Q5_K_M').level).toBe('high');
    expect(quantQuality('5bit').level).toBe('high');
  });

  it('assigns balanced to Q4/IQ4 sweet spot (unsloth default)', () => {
    expect(quantQuality('Q4_K_M').level).toBe('balanced');
    expect(quantQuality('UD-Q4_K_XL').level).toBe('balanced');
    expect(quantQuality('IQ4_XS').level).toBe('balanced');
    expect(quantQuality('4bit').level).toBe('balanced');
  });

  it('assigns compact to low-bit quants', () => {
    expect(quantQuality('Q3_K_L').level).toBe('compact');
    expect(quantQuality('UD-Q2_K_XL').level).toBe('compact');
    expect(quantQuality('IQ2_M').level).toBe('compact');
    expect(quantQuality('TQ1_0').level).toBe('compact');
    expect(quantQuality('2bit').level).toBe('compact');
  });

  it('treats non-quant notation as unknown', () => {
    expect(quantQuality('').level).toBe('unknown');
    expect(quantQuality(null).level).toBe('unknown');
    expect(quantQuality('Active').level).toBe('unknown');
    expect(quantQuality('N/A').level).toBe('unknown');
    expect(quantQuality('some-random-string').level).toBe('unknown');
  });

  it('is case insensitive', () => {
    expect(quantQuality('q4_k_m').level).toBe('balanced');
    expect(quantQuality('ud-q8_k_xl').level).toBe('premium');
    expect(quantQuality('4BIT').level).toBe('balanced');
  });

  it('exposes grade letters and labels for the badge UI', () => {
    expect(quantQuality('Q8_0').grade).toBe('P');
    expect(quantQuality('Q5_K_S').grade).toBe('H');
    expect(quantQuality('Q4_K_M').grade).toBe('B');
    expect(quantQuality('Q2_K').grade).toBe('C');
    expect(quantQuality('').grade).toBe('?');
    expect(quantQuality('Q4_K_M').label).toContain('스위트스팟');
  });
});
