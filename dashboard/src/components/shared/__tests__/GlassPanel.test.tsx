/**
 * GlassPanel Tests
 * =================
 * Tests for the GlassPanel shared component — rendering with title, count, subtitle, children.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GlassPanel from '../GlassPanel';

describe('GlassPanel', () => {
  it('renders the title', () => {
    render(<GlassPanel title="Test Panel">Content</GlassPanel>);
    expect(screen.getByText('Test Panel')).toBeInTheDocument();
  });

  it('renders children', () => {
    render(<GlassPanel title="Test"><span data-testid="child">Child Content</span></GlassPanel>);
    expect(screen.getByTestId('child')).toHaveTextContent('Child Content');
  });

  it('shows count with prefix when count is provided', () => {
    render(<GlassPanel title="Data" count={5}>Content</GlassPanel>);
    expect(screen.getByText('5개 추출')).toBeInTheDocument();
  });

  it('shows subtitle instead of count when subtitle is provided', () => {
    render(<GlassPanel title="Data" subtitle="custom">Content</GlassPanel>);
    expect(screen.getByText('custom')).toBeInTheDocument();
  });

  it('shows nothing in the right span when no count or subtitle', () => {
    const { container } = render(<GlassPanel title="Plain">Content</GlassPanel>);
    // The right span should be empty string
    const spans = container.querySelectorAll('span');
    const rightSpan = Array.from(spans).find(s => s.style.marginLeft === 'auto');
    expect(rightSpan?.textContent).toBe('');
  });

  it('renders complex JSX children', () => {
    render(
      <GlassPanel title="Complex">
        <ul>
          <li>Item 1</li>
          <li>Item 2</li>
        </ul>
      </GlassPanel>,
    );
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
  });
});
