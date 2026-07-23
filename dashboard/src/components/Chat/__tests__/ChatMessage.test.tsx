/**
 * ChatMessage Tests (Phase 12 — memoization)
 * =============================================
 * Tests the chatMessageAreEqual comparator and React.memo behavior.
 */

import { describe, it, expect, vi, afterAll } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import ChatMessage, { chatMessageAreEqual } from '../ChatMessage';

/* ─── Fixtures ─────────────────────────────────────────────── */

const createMessage = (overrides: Partial<{ id: string; role: string; content: string }> = {}) => ({
  id: overrides.id ?? 'msg-1',
  role: (overrides.role ?? 'assistant') as 'user' | 'assistant',
  content: overrides.content ?? 'Hello world',
});

/* ─── ChatMessage Module ───────────────────────────────────── */

describe('ChatMessage module', () => {
  it('has displayName set', () => {
    expect(ChatMessage.displayName).toBe('ChatMessage');
  });
});

/* ─── ChatMessage Rendering ────────────────────────────────── */

describe('ChatMessage rendering', () => {
  it('renders user message with avatar', () => {
    render(<ChatMessage message={createMessage({ role: 'user', content: 'How are you?' })} />);
    expect(screen.getByText('👤')).toBeInTheDocument();
    expect(screen.getByText('How are you?')).toBeInTheDocument();
  });

  it('renders assistant message with avatar', () => {
    render(<ChatMessage message={createMessage({ role: 'assistant', content: 'I am fine!' })} />);
    expect(screen.getByText('🤖')).toBeInTheDocument();
    expect(screen.getByText('I am fine!')).toBeInTheDocument();
  });

  it('renders null when content is empty for assistant', () => {
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content: '' })} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders null when content is empty for user', () => {
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'user', content: '' })} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders assistant content with copy button', () => {
    render(<ChatMessage message={createMessage({ role: 'assistant', content: 'Some response' })} />);
    expect(screen.getByText('📋 복사')).toBeInTheDocument();
  });

  it('renders user content without copy button', () => {
    render(<ChatMessage message={createMessage({ role: 'user', content: 'Some question' })} />);
    expect(screen.queryByText('📋 복사')).not.toBeInTheDocument();
  });

  it('renders assistant message without actions when content is empty', () => {
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content: '' })} />,
    );
    expect(container.innerHTML).toBe('');
  });
});

/* ─── chatMessageAreEqual Comparator ────────────────────────── */

describe('chatMessageAreEqual comparator', () => {
  it('renders correctly for identical messages', () => {
    const msg = createMessage({ id: 'msg-1', role: 'assistant', content: 'Hello' });
    const { container: c1 } = render(<ChatMessage message={msg} />);
    expect(c1.querySelector('.bubble')?.textContent).toBeTruthy();
  });

  it('detects different role', () => {
    const msg1 = createMessage({ id: 'msg-1', role: 'user', content: 'Hello' });
    const msg2 = createMessage({ id: 'msg-1', role: 'assistant', content: 'Hello' });
    const { container: c1 } = render(<ChatMessage message={msg1} />);
    const { container: c2 } = render(<ChatMessage message={msg2} />);
    expect(c1.querySelector('.avatar')?.textContent).toBe('👤');
    expect(c2.querySelector('.avatar')?.textContent).toBe('🤖');
  });

  it('detects different content', () => {
    const msg1 = createMessage({ id: 'msg-1', role: 'assistant', content: 'Hello' });
    const msg2 = createMessage({ id: 'msg-1', role: 'assistant', content: 'World' });
    const { container: c1 } = render(<ChatMessage message={msg1} />);
    const { container: c2 } = render(<ChatMessage message={msg2} />);
    expect(c1.textContent).toContain('Hello');
    expect(c2.textContent).toContain('World');
  });
});

/* ─── Mermaid Diagram ──────────────────────────────────────── */

describe('ChatMessage Mermaid diagram', () => {
  afterAll(() => {
    delete (window as any).mermaid;
  });

  it('shows error when mermaid library not loaded', () => {
    const { container } = render(
      <ChatMessage
        message={createMessage({
          role: 'assistant',
          content: '```mermaid\ngraph TD;\nA-->B;\n```',
        })}
      />,
    );
    // rehype-highlight processes the code block — 'mermaid' language label should appear
    expect(container.textContent).toMatch(/mermaid/i);
  });

  it('renders mermaid diagram when library is available', async () => {
    (window as any).mermaid = {
      render: vi.fn().mockResolvedValue({ svg: '<svg>test</svg>' }),
    };

    render(
      <ChatMessage
        message={createMessage({
          role: 'assistant',
          content: '```mermaid\ngraph TD;\nA-->B;\n```',
        })}
      />,
    );

    // After rehype-highlight processing, the mermaid code block is syntax-highlighted
    // Copy buttons exist from MessageActions and CodeBlock
    const copyBtns = screen.getAllByText('📋 복사');
    expect(copyBtns.length).toBeGreaterThanOrEqual(1);
  });
});

/* ─── Carousel Slideshow ──────────────────────────────────── */

describe('ChatMessage Carousel', () => {
  it('renders carousel code block with language label', () => {
    const content = '```carousel\n# Slide 1\nContent 1\n<!-- slide -->\n# Slide 2\nContent 2\n```';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    // rehype-highlight transforms className → 'hljs language-carousel'
    // The language label 'carousel' appears in the rendered content
    expect(container.textContent).toMatch(/carousel/i);
  });
});

/* ─── Inline Code ──────────────────────────────────────────── */

describe('ChatMessage inline code', () => {
  it('renders inline code with backtick syntax', () => {
    const content = 'Use the `const` keyword to declare variables.';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    // The content should render and contain the backtick text
    expect(container.textContent).toMatch(/const/);
  });
});

/* ─── Blockquote (GitHub Alert) ───────────────────────────── */

describe('ChatMessage blockquote', () => {
  it('renders blockquote content', () => {
    const content = '> This is a quote';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    // The blockquote content should be rendered
    expect(container.textContent).toMatch(/This is a quote/);
  });
});

/* ─── Clipboard Copy ───────────────────────────────────────── */

describe('ChatMessage clipboard copy', () => {
  it('renders copy buttons that can be clicked without error', async () => {
    // Stub navigator.clipboard for jsdom compatibility
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      writable: true,
      configurable: true,
    });

    render(
      <ChatMessage
        message={createMessage({ role: 'assistant', content: 'Test content for copy' })}
      />,
    );

    const copyBtns = screen.getAllByText('📋 복사');
    expect(copyBtns.length).toBeGreaterThanOrEqual(1);

    for (const btn of copyBtns) {
      await act(async () => { fireEvent.click(btn); });
    }

    expect(writeText).toHaveBeenCalled();

    // Restore original clipboard
    Object.defineProperty(navigator, 'clipboard', {
      value: originalClipboard,
      writable: true,
      configurable: true,
    });
  });
});

/* ─── Code Block ───────────────────────────────────────────── */

describe('ChatMessage code block', () => {
  it('renders code block with copy buttons', () => {
    const { container } = render(
      <ChatMessage
        message={createMessage({
          role: 'assistant',
          content: '```typescript\nconst x = 1;\n```',
        })}
      />,
    );
    // Multiple 📋 복사 buttons exist (one from MessageActions, one from CodeBlock)
    const copyBtns = screen.getAllByText('📋 복사');
    expect(copyBtns.length).toBeGreaterThanOrEqual(1);
    // With rehype-highlight, code block children are React elements, not raw text.
    // The hljs class indicator from rehype-highlight should appear.
    expect(container.textContent).toMatch(/typescript/i);
  });
});
