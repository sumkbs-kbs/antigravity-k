/**
 * EmptyData Tests
 * ================
 * Tests for the EmptyData shared component — message rendering.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import EmptyData from '../EmptyData';

describe('EmptyData', () => {
  it('renders the empty message', () => {
    render(<EmptyData msg="No data available" />);
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  it('renders Korean message', () => {
    render(<EmptyData msg="추출된 데이터가 없습니다" />);
    expect(screen.getByText('추출된 데이터가 없습니다')).toBeInTheDocument();
  });

  it('renders within a container div', () => {
    const { container } = render(<EmptyData msg="Hello" />);
    const div = container.firstChild as HTMLElement;
    expect(div.tagName).toBe('DIV');
    expect(div.style.textAlign).toBe('center');
  });
});
