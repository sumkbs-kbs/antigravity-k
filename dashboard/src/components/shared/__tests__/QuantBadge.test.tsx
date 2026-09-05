/**
 * QuantBadge Tests (Phase 32)
 * ============================
 * 공유 컴포넌트 통합 후에도 두 표면의 기존 계약(클래스·툴팁·텍스트)이 유지되는지 검증.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import QuantBadge, { quantBadgeClasses } from '../QuantBadge';

describe('QuantBadge', () => {
  it('chip variant shows the quantization token with legacy badge-quant classes', () => {
    render(<QuantBadge quantization="UD-Q4_K_XL" variant="chip" />);
    const chip = screen.getByText('UD-Q4_K_XL');
    expect(chip).toHaveClass('quant-badge', 'chip', 'badge-quant', 'q-balanced');
    expect(chip).toHaveAttribute('title', 'UD-Q4_K_XL — 균형 — 크기·품질 스위트스팟');
  });

  it('chip variant exposes the one-letter grade via data-grade (::before icon)', () => {
    render(<QuantBadge quantization="UD-Q4_K_XL" variant="chip" />);
    const chip = screen.getByText('UD-Q4_K_XL');
    expect(chip).toHaveAttribute('data-grade', 'B');
  });

  it('grade variant shows the single-letter grade with legacy quant-quality-badge classes', () => {
    render(<QuantBadge quantization="Q8_0" variant="grade" />);
    const badge = screen.getByText('P');
    expect(badge).toHaveClass('quant-badge', 'grade', 'quant-quality-badge', 'q-premium');
    expect(badge).toHaveAttribute('title', 'Q8_0 — 프리미엄 — 원본 손실 거의 없음');
  });

  it('defaults to chip variant', () => {
    render(<QuantBadge quantization="4bit" />);
    expect(screen.getByText('4bit')).toHaveClass('chip');
  });

  it('maps each level to its grade letter', () => {
    const cases: Array<[string, string]> = [
      ['Q8_0', 'P'],
      ['Q6_K', 'H'],
      ['Q4_K', 'B'],
      ['Q2_K', 'C'],
    ];
    for (const [token, grade] of cases) {
      const { unmount } = render(<QuantBadge quantization={token} variant="grade" />);
      expect(screen.getByText(grade)).toBeInTheDocument();
      unmount();
    }
  });

  it('chip variant carries the matching data-grade for each level', () => {
    const cases: Array<[string, string]> = [
      ['Q8_0', 'P'],
      ['Q6_K', 'H'],
      ['Q4_K', 'B'],
      ['Q2_K', 'C'],
    ];
    for (const [token, grade] of cases) {
      const { unmount } = render(<QuantBadge quantization={token} variant="chip" />);
      expect(screen.getByText(token)).toHaveAttribute('data-grade', grade);
      unmount();
    }
  });

  it('quantBadgeClasses appends extra classNames', () => {
    expect(quantBadgeClasses('balanced', 'chip', 'extra-here')).toContain('extra-here');
  });
});
