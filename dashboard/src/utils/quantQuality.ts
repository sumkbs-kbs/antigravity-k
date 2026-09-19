/**
 * quantQuality — GGUF/MLX 양자화 품질 등급 산출
 * ===============================================================
 * 벤치마킹 출처: unsloth Dynamic GGUF 품질 가이드.
 * 레이어별 혼합 정밀도 양자화(UD-*)는 동일 비트의 정적 양자화보다
 * 품질이 높으므로 등급 산정 시 우대한다.
 *
 * Conformance (Phase 46): tests/fixtures/quant_quality_conformance.json 하나를
 * 파이썬 쌍생 구현(engine/quant_quality.py)과 공유 검증한다 — 이 파일의 토큰 셋·
 * 등급·라벨을 바꿀 때는 fixture + 양쪽 테스트를 함께 갱신할 것.
 *
 * 등급 체계:
 *  - premium:  Q8_0 / F16 / BF16 / 8bit — 원본 손실 거의 없음
 *  - high:     Q6_K / Q5_K / 6bit / 5bit — 품질 저하 미미
 *  - balanced: Q4_K / IQ4 / 4bit — 크기·품질 스위트스팟 (unsloth 권장 기본값 UD-Q4_K_XL)
 *  - compact:  Q3 / Q2 / IQ2 / TQ / 3bit / 2bit — 용량 우선, 품질 희생
 *  - unknown:  파싱 실패 / 미표기
 */

export type QuantQualityLevel = 'premium' | 'high' | 'balanced' | 'compact' | 'unknown';

export interface QuantQualityInfo {
  level: QuantQualityLevel;
  /** 등급 한 글자 (P/H/B/C) — 배지 아이콘용 */
  grade: string;
  /** 사용자 설명 */
  label: string;
}

const PREMIUM_RE = /^(UD-)?(Q8|F16|BF16|FP16)|^\d?8bit$/i;
const HIGH_RE = /^(UD-)?(Q6|Q5)|^[65]bit$/i;
const BALANCED_RE = /^(UD-)?(Q4|IQ4)|^4bit$/i;
const COMPACT_RE = /^(UD-)?(Q3|Q2|IQ2|IQ1|TQ)|^[23]bit$/i;

const INFO: Record<QuantQualityLevel, QuantQualityInfo> = {
  premium: { level: 'premium', grade: 'P', label: '프리미엄 — 원본 손실 거의 없음' },
  high: { level: 'high', grade: 'H', label: '높음 — 품질 저하 미미' },
  balanced: { level: 'balanced', grade: 'B', label: '균형 — 크기·품질 스위트스팟' },
  compact: { level: 'compact', grade: 'C', label: '컴팩트 — 용량 우선' },
  unknown: { level: 'unknown', grade: '?', label: '양자화 정보 없음' },
};

export function quantQuality(quantization: string | null | undefined): QuantQualityInfo {
  const raw = (quantization ?? '').trim();
  if (!raw) return INFO.unknown;

  // "Active"/"N/A" 등 비양자화 표기 처리
  if (/^active$/i.test(raw) || /^n\/?a$/i.test(raw)) return INFO.unknown;

  if (PREMIUM_RE.test(raw)) return INFO.premium;
  if (HIGH_RE.test(raw)) return INFO.high;
  if (BALANCED_RE.test(raw)) return INFO.balanced;
  if (COMPACT_RE.test(raw)) return INFO.compact;
  return INFO.unknown;
}
