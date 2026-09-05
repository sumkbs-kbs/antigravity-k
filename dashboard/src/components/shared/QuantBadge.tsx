/**
 * QuantBadge — 양자화 품질 등급 배지 (Phase 32)
 * ==============================================
 * ChatPage 모델 칩과 Model Hub 등급 배지가 같은 마크업/팔레트를 쓰도록 통합.
 * 등급 산정은 quantQuality util 단일 진실원 (Python 쌍생: engine/quant_quality.py).
 *
 * variant:
 *  - "chip"  — 양자화 토큰을 그대로 표시 (ChatPage 팝오버; UD-Q4_K_XL 자체가 식별자)
 *  - "grade" — 등급 한 글자(P/H/B/C/?) 표시 (Model Hub 카드; 좁은 spec 행용)
 */

import React from 'react';
import { quantQuality } from '../../utils/quantQuality';

export interface QuantBadgeProps {
  /** GGUF/MLX 양자화 토큰 (예: UD-Q4_K_XL, 4bit, Q8_0) */
  quantization: string;
  /** 표시 형태 — chip: 토큰 텍스트, grade: 등급 한 글자 (기본 chip) */
  variant?: 'chip' | 'grade';
  /** 추가 클래스 */
  className?: string;
}

export function quantBadgeClasses(level: string, variant: string, extra?: string): string {
  const base = variant === 'grade' ? 'quant-badge grade' : 'quant-badge chip';
  // 레거시 클래스 병기 — 기존 CSS 선택자/테스트 호환 유지
  const legacy = variant === 'grade' ? 'quant-quality-badge' : 'badge-quant';
  return [base, legacy, `q-${level}`, extra].filter(Boolean).join(' ');
}

const QuantBadge: React.FC<QuantBadgeProps> = ({ quantization, variant = 'chip', className }) => {
  const info = quantQuality(quantization);
  return (
    <span
      className={quantBadgeClasses(info.level, variant, className)}
      title={`${quantization} — ${info.label}`}
      data-grade={info.grade}
    >
      {variant === 'grade' ? info.grade : quantization}
    </span>
  );
};

export default QuantBadge;
