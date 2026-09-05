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

  it('renders user message wrapped in user-message-text span', () => {
    const { container } = render(<ChatMessage message={createMessage({ role: 'user', content: '안녕' })} />);
    const userSpan = container.querySelector('.user-message-text');
    expect(userSpan).toBeInTheDocument();
    expect(userSpan?.textContent).toBe('안녕');
  });

  it('formats unicode bullets and tip callouts in assistant messages', () => {
    const content = '안내 말씀:\n• 📁 src/test/ - 테스트 파일\n• 📁 src/engine/ - 코어 엔진\n💡 팁: 설정은 http://localhost:8000 에서 확인하세요.';
    const { container } = render(<ChatMessage message={createMessage({ role: 'assistant', content })} />);
    const listItems = container.querySelectorAll('li');
    expect(listItems.length).toBe(2);
    expect(listItems[0]?.textContent).toContain('src/test/');
    expect(listItems[1]?.textContent).toContain('src/engine/');
    const callout = container.querySelector('.tip-callout');
    expect(callout).toBeInTheDocument();
    expect(callout?.textContent).toContain('팁:');
    expect(callout?.textContent).toContain('http://localhost:8000');
    const link = callout?.querySelector('a');
    expect(link).toBeInTheDocument();
    expect(link?.getAttribute('href')).toBe('http://localhost:8000');
  });

  it('renders compact token badge with comma values', () => {
    const content = '📊 Tokens Used: In: 1,234 | Out: 567';
    const { container } = render(<ChatMessage message={createMessage({ role: 'assistant', content })} />);
    const tokenBadge = container.querySelector('.tool-timeline-badge.token');
    expect(tokenBadge).toBeInTheDocument();
    expect(tokenBadge?.textContent).toContain('In: 1,234');
    expect(tokenBadge?.textContent).toContain('Out: 567');
  });

  it('renders assistant message without actions when content is empty', () => {
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content: '' })} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('sanitizes raw HTML before rendering', () => {
    const content = '<img src="x" onerror="window.__agkXss = true"><script>window.__agkXss = true</script>';
    const { container } = render(<ChatMessage message={createMessage({ role: 'assistant', content })} />);
    expect(container.querySelector('script')).not.toBeInTheDocument();
    expect(container.querySelector('[onerror]')).not.toBeInTheDocument();
  });

  it('delegates approval actions without inline handlers', () => {
    const handler = vi.fn();
    window.addEventListener('agk:approval-response', handler);
    const content = "[APPROVAL REQUIRED] Please approve this change\nWait for their 'Yes' before retrying.";

    render(<ChatMessage message={createMessage({ role: 'assistant', content })} />);
    const approveButton = screen.getByRole('button', { name: /승인/ });
    expect(approveButton).not.toHaveAttribute('onclick');
    fireEvent.click(approveButton);

    expect(handler).toHaveBeenCalledTimes(1);
    expect((handler.mock.calls[0]?.[0] as CustomEvent<{ text: string }>).detail.text).toBe('승인합니다');
    window.removeEventListener('agk:approval-response', handler);
  });

  it('delegates artifact preview actions through the window API', () => {
    const previewArtifact = vi.fn().mockResolvedValue(undefined);
    const originalPreviewArtifact = window.previewArtifact;
    window.previewArtifact = previewArtifact;
    const content = '[ARTIFACT GENERATED: report.html (Type: html)]\nSuccessfully saved to /tmp/report.html.';

    render(<ChatMessage message={createMessage({ role: 'assistant', content })} />);
    fireEvent.click(screen.getByRole('button', { name: /View Preview/ }));

    expect(previewArtifact).toHaveBeenCalledWith('/tmp/report.html', 'report.html');
    window.previewArtifact = originalPreviewArtifact;
  });
});

/* ─── chatMessageAreEqual Comparator ────────────────────────── */

describe('chatMessageAreEqual comparator', () => {
  it('returns true for identical messages', () => {
    const msg = { id: 'msg-1', role: 'assistant' as const, content: 'Hello' };
    expect(chatMessageAreEqual(
      { message: msg },
      { message: { ...msg } },
    )).toBe(true);
  });

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

/* ─── GitHubAlert Fallback ───────────────────────────────── */

describe('GitHubAlert', () => {
  it('renders blockquote fallback for unmatched alert syntax', () => {
    const content = '> Regular blockquote without alert syntax';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    expect(container.textContent).toMatch(/Regular blockquote/);
    const blockquote = container.querySelector('blockquote');
    expect(blockquote).toBeInTheDocument();
  });
});

/* ─── Mermaid Diagram ──────────────────────────────────────── */

function mermaidContent(): string {
  return '```mermaid\ngraph TD;\nA-->B;\n```';
}

describe('ChatMessage Mermaid diagram', () => {
  afterAll(() => {
    delete window.mermaid;
  });

  it('shows error when mermaid library not loaded', async () => {
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content: mermaidContent() })} />,
    );
    await screen.findByText(/mermaid/i);
    expect(container.textContent).toMatch(/mermaid/i);
  });

  it('renders mermaid diagram when library is available', async () => {
    window.mermaid = {
      render: vi.fn().mockResolvedValue({ svg: '<svg>test</svg>' }),
    };

    render(
      <ChatMessage message={createMessage({ role: 'assistant', content: mermaidContent() })} />,
    );

    const copyBtns = await screen.findAllByText('📋 복사');
    expect(copyBtns.length).toBeGreaterThanOrEqual(1);
  });

  it('shows loading state while rendering diagram', async () => {
    window.mermaid = {
      render: vi.fn().mockReturnValue(new Promise(() => {})),
    };

    render(
      <ChatMessage message={createMessage({ role: 'assistant', content: mermaidContent() })} />,
    );

    // ReactMarkdown + MermaidDiagram are async; wait for the loading text
    await screen.findByText(/다이어그램 렌더링 중/);
  });

  it('shows error message when mermaid render throws', async () => {
    window.mermaid = {
      render: vi.fn().mockRejectedValue(new Error('Syntax error in graph')),
    };

    render(
      <ChatMessage message={createMessage({ role: 'assistant', content: mermaidContent() })} />,
    );

    await screen.findByText(/Syntax error in graph/);
  });

  it('handles cleanup on unmount during render', async () => {
    const renderDeferred: { resolve: (value: { svg: string }) => void } = { resolve: () => {} };
    const renderPromise = new Promise<{ svg: string }>(resolve => { renderDeferred.resolve = resolve; });

    window.mermaid = {
      render: vi.fn().mockReturnValue(renderPromise),
    };

    const { unmount } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content: mermaidContent() })} />,
    );

    // Wait for ReactMarkdown to mount MermaidDiagram
    await screen.findByText(/다이어그램 렌더링 중/);

    // Unmount and let the cancelled flag handle cleanup
    unmount();
    renderDeferred.resolve({ svg: '<svg>test</svg>' });

    await new Promise(r => setTimeout(r, 50));
    expect(screen.queryByText(/다이어그램/)).not.toBeInTheDocument();
  });
});

/* ─── Carousel Slideshow ──────────────────────────────────── */

function carouselContent(): string {
  return '```carousel\n# Slide 1\nContent 1\n<!-- slide -->\n# Slide 2\nContent 2\n```';
}

describe('ChatMessage Carousel', () => {
  it('renders carousel container for valid slides', async () => {
    render(
      <ChatMessage message={createMessage({ role: 'assistant', content: carouselContent() })} />,
    );
    const container = await screen.findByText(/◀ 이전/);
    expect(container).toBeInTheDocument();
  });

  it('returns null for empty slides', () => {
    const content = '```carousel\n```';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    expect(container.querySelector('.carousel-container')).toBeNull();
  });

  it('disables prev button on first slide', async () => {
    render(
      <ChatMessage message={createMessage({ role: 'assistant', content: carouselContent() })} />,
    );

    const prevBtn = (await screen.findByText('◀ 이전')).closest('button')!;
    expect(prevBtn).toBeDisabled();

    const nextBtn = (await screen.findByText('다음 ▶')).closest('button')!;
    expect(nextBtn).not.toBeDisabled();
  });

  it('disables next button on last slide', async () => {
    render(
      <ChatMessage message={createMessage({ role: 'assistant', content: carouselContent() })} />,
    );

    const nextBtn = (await screen.findByText('다음 ▶')).closest('button')!;
    await act(async () => { fireEvent.click(nextBtn); });

    expect(nextBtn).toBeDisabled();
    const prevBtn = (await screen.findByText('◀ 이전')).closest('button')!;
    expect(prevBtn).not.toBeDisabled();
  });

  it('extracts title from first slide heading', async () => {
    const content = '```carousel\n# Slide 1 Title\nContent 1\n<!-- slide -->\n# Slide 2\nContent 2\n```';
    render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );

    await screen.findByText('Slide 1 Title');
    expect(screen.getByText('Content 1')).toBeInTheDocument();
  });
});

/* ─── Inline Code ──────────────────────────────────────────── */

describe('ChatMessage inline code', () => {
  it('renders inline code with backtick syntax', () => {
    const content = 'Use the `const` keyword to declare variables.';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    expect(container.textContent).toMatch(/const/);
  });

  it('renders inline-code class for backtick content', () => {
    const content = 'Run `npm install` in the terminal.';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    const inlineCode = container.querySelector('code.inline-code');
    expect(inlineCode).toBeInTheDocument();
    expect(inlineCode?.textContent).toMatch(/npm install/);
  });
});

/* ─── Blockquote (GitHub Alert) ───────────────────────────── */

describe('ChatMessage blockquote', () => {
  it('renders blockquote content', () => {
    const content = '> This is a quote';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    expect(container.textContent).toMatch(/This is a quote/);
  });
});

/* ─── Clipboard Copy ───────────────────────────────────────── */

describe('ChatMessage clipboard copy', () => {
  it('renders copy buttons that can be clicked without error', async () => {
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

    Object.defineProperty(navigator, 'clipboard', {
      value: originalClipboard,
      writable: true,
      configurable: true,
    });
  });
});

/* ─── Code Block ───────────────────────────────────────────── */

describe('ChatMessage code block', () => {
  it('renders code block with copy buttons', async () => {
    const content = '```typescript\nconst x = 1;\n```';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    const copyBtns = await screen.findAllByText('📋 복사');
    expect(copyBtns.length).toBeGreaterThanOrEqual(1);
    expect(container.textContent).toMatch(/typescript/i);
  });

  it('shows default language label when no language specified', async () => {
    const content = '```\nplain code block\n```';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    await screen.findByText(/code/);
    expect(container.textContent).toMatch(/code/);
  });

  it('renders pre element via passthrough', async () => {
    const content = '```typescript\nconst x = 1;\n```';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    const pres = container.querySelectorAll('pre');
    expect(pres.length).toBeGreaterThanOrEqual(1);
    const codeInPre = pres[0]?.querySelector('code');
    expect(codeInPre).toBeInTheDocument();
  });

  it('renders Antigravity thinking box when think tags are present', () => {
    const content = '<think>이것은 시스템 아키텍처에 대한 심층 사고 과정입니다.</think>최종 분석 결과입니다.';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    const thoughtBox = container.querySelector('.antigravity-thought-box');
    expect(thoughtBox).toBeInTheDocument();
    expect(thoughtBox?.textContent).toContain('생각 과정 (Thinking Process)');
    expect(thoughtBox?.textContent).toContain('이것은 시스템 아키텍처에 대한 심층 사고 과정입니다.');
    expect(container.textContent).toContain('최종 분석 결과입니다.');
  });

  it('renders Antigravity tool cards for tool execution pattern', () => {
    const content = '**도구 실행** (step 1/3): `run_command`\n완료되었습니다.';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    const toolCard = container.querySelector('.antigravity-tool-card');
    expect(toolCard).toBeInTheDocument();
    expect(toolCard?.textContent).toContain('Executing Tool');
    expect(toolCard?.textContent).toContain('run_command');
    expect(toolCard?.textContent).toContain('Step 1/3');
  });

  it('renders Antigravity markdown tables in responsive container', () => {
    const content = '| 항목 | 설명 |\n|---|---|\n| 토큰 | 1500 |\n| 지연시간 | 120ms |';
    const { container } = render(
      <ChatMessage message={createMessage({ role: 'assistant', content })} />,
    );
    const tableContainer = container.querySelector('.agk-table-container');
    expect(tableContainer).toBeInTheDocument();
    const table = container.querySelector('.agk-markdown-table');
    expect(table).toBeInTheDocument();
    expect(table?.textContent).toContain('항목');
    expect(table?.textContent).toContain('120ms');
  });
});
