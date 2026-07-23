/**
 * StatBox Tests
 * ==============
 * Tests for the StatBox shared component — label, value, bold, color.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatBox from '../StatBox';

describe('StatBox', () => {
  it('renders label and value', () => {
    render(<StatBox label="종가" value="₩943,000" />);
    expect(screen.getByText('종가')).toBeInTheDocument();
    expect(screen.getByText('₩943,000')).toBeInTheDocument();
  });

  it('applies bold style when bold is true', () => {
    render(<StatBox label="종가" value="₩943,000" bold />);
    const valueEl = screen.getByText('₩943,000');
    expect(valueEl.style.fontWeight).toBe('600');
  });

  it('uses normal weight when bold is not set', () => {
    render(<StatBox label="시가" value="₩930,000" />);
    const valueEl = screen.getByText('₩930,000');
    expect(valueEl.style.fontWeight).toBe('400');
  });

  it('applies custom color', () => {
    render(<StatBox label="등락률" value="+1.51%" color="#10b981" />);
    const valueEl = screen.getByText('+1.51%');
    // jsdom may convert #hex to rgb() format with spaces
    const color = valueEl.style.color.replace(/\s/g, '');
    expect(color).toMatch(/^(#10b981|rgb\(16,185,129\))$/i);
  });

  it('uses default text color when no color provided', () => {
    render(<StatBox label="기본" value="값" />);
    const valueEl = screen.getByText('값');
    expect(valueEl.style.color).toBe('var(--text-primary)');
  });

  it('uses larger font size for bold values', () => {
    render(<StatBox label="종가" value="₩943,000" bold />);
    const valueEl = screen.getByText('₩943,000');
    expect(valueEl.style.fontSize).toBe('14px');
  });

  it('uses smaller font size for normal values', () => {
    render(<StatBox label="시가" value="₩930,000" />);
    const valueEl = screen.getByText('₩930,000');
    expect(valueEl.style.fontSize).toBe('13px');
  });
});
