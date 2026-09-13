/**
 * ChatMessage — Individual message bubble with rendering
 * Supports: agent badges, tool timeline, artifact preview, approval UI,
 * code syntax highlighting, markdown tables, copy actions,
 * GitHub Alerts, Mermaid diagrams, and Carousel slideshows.
 */

import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { ChatMessage as ChatMessageType } from '../../stores/chatStore';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { preprocessContent, sanitizeMarkdown } from '../../utils/formatContent';
// CR-09(F05): mermaid는 CDN 전역이 아니라 다이어그램을 그릴 때 로컬에서 지연 로드한다.
import { loadMermaid } from '../../utils/mermaidRuntime';

interface Props {
  message: ChatMessageType;
}

const markdownSanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames ?? []),
    'button',
    'details',
    'summary',
    'div',
    'span',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
  ],
  attributes: {
    ...defaultSchema.attributes,
    details: ['open', 'className', 'style'],
    summary: ['className', 'style'],
    div: ['className', 'style', 'data*'],
    span: ['className', 'style', 'data*'],
    button: [
      ...(defaultSchema.attributes?.button ?? []),
      'type',
      'className',
      'style',
      'data*',
    ],
    '*': [
      ...(defaultSchema.attributes?.['*'] ?? []),
      ['className', /^[A-Za-z0-9_-]+$/],
      'style',
      'data*',
    ],
  },
};

// ─── GitHub Alert Blockquote (fallback — main conversion in formatContent.ts) ──
const GitHubAlert: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // The preprocessing in formatContent.ts already converts > [!TYPE] blocks
  // into styled HTML <blockquote> elements. This component is a fallback
  // for any blockquotes that weren't matched by the preprocessor.
  return <blockquote>{children}</blockquote>;
};

// ─── Mermaid Diagram ──────────────────────────────────────────────
declare global {
  interface Window {
    previewArtifact?: (filePath: string, fileName: string) => Promise<void>;
  }
}

const MermaidDiagram: React.FC<{ code: string }> = ({ code }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const renderId = `mermaid-${useId().replaceAll(':', '')}`;

  useEffect(() => {
    let cancelled = false;

    const render = async () => {
      try {
        if (!containerRef.current) return;
        /*
         * CR-09(F05): CDN의 window.mermaid 대신 로컬 의존성을 지연 로드한다.
         * 로드 실패는 아래 catch가 그대로 사용자 오류 화면으로 보여준다.
         */
        const mermaid = await loadMermaid();
        if (!containerRef.current) return;
        containerRef.current.innerHTML = '';
        const { svg } = await mermaid.render(renderId, code);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError(null);
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : String(error);
          setError(message || 'Mermaid render failed');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    render();
    return () => { cancelled = true; };
  }, [code, renderId]);

  if (error) {
    return (
      <div className="mermaid-container">
        <div className="mermaid-error">
          ⚠️ Mermaid 렌더링 오류: {error}
          <pre style={{ marginTop: 8, fontSize: 11, opacity: 0.7 }}>{code}</pre>
        </div>
      </div>
    );
  }

  return (
    <div className="mermaid-container">
      {loading && <div className="mermaid-loading">🔄 다이어그램 렌더링 중...</div>}
      <div ref={containerRef} style={{ minHeight: loading ? 0 : 40 }} />
    </div>
  );
};

// ─── Carousel Slideshow ───────────────────────────────────────────
const CarouselView: React.FC<{ slides: string[] }> = ({ slides }) => {
  const [current, setCurrent] = useState(0);

  if (slides.length === 0) return null;

  const slide = slides[current];
  const lines = slide.split('\n');
  const title = lines[0]?.replace(/^#+\s*/, '') || '';
  const body = lines.slice(1).join('\n');

  return (
    <div className="carousel-container">
      <div className="carousel-nav">
        <button
          type="button"
          className="carousel-nav-btn"
          disabled={current === 0}
          onClick={() => setCurrent(c => Math.max(0, c - 1))}
        >
          ◀ 이전
        </button>
        <div className="carousel-dots">
          {slides.map((_, i) => (
            <button
              key={slides[i]}
              type="button"
              className={`carousel-dot ${i === current ? 'active' : ''}`}
              onClick={() => setCurrent(i)}
              aria-label={`슬라이드 ${i + 1}로 이동`}
            />
          ))}
        </div>
        <button
          type="button"
          className="carousel-nav-btn"
          disabled={current === slides.length - 1}
          onClick={() => setCurrent(c => Math.min(slides.length - 1, c + 1))}
        >
          다음 ▶
        </button>
      </div>
      <div className="carousel-slide">
        {title && <h4>{title}</h4>}
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          rehypePlugins={[rehypeHighlight, rehypeRaw, [rehypeSanitize, markdownSanitizeSchema]]}
        >
          {body}
        </ReactMarkdown>
      </div>
    </div>
  );
};

/** Extract raw code text from React children that may be wrapped in syntax-highlighting spans. */
function extractCodeText(children: React.ReactNode): string {
  if (typeof children === 'string') return children;
  if (typeof children === 'number') return String(children);
  if (React.isValidElement<{ children?: React.ReactNode }>(children)) {
    return extractCodeText(children.props.children);
  }
  if (Array.isArray(children)) {
    return children.map(extractCodeText).join('');
  }
  return '';
}

/**
 * CR-09: 하이라이트 span 트리를 렌더할 때 마지막 개행을 제거한다. 예전에는 평문으로
 * 치환하면서 `\n` 하나를 떼어냈기 때문에, 그대로 두면 코드 블록 아래에 빈 줄이 생긴다.
 */
function trimTrailingNewline(children: React.ReactNode): React.ReactNode {
  if (typeof children === 'string') return children.replace(/\n$/, '');
  if (Array.isArray(children)) {
    const last = children.at(-1);
    if (typeof last === 'string') return [...children.slice(0, -1), last.replace(/\n$/, '')];
  }
  return children;
}

/** Extract the language name from a className like 'hljs language-typescript'. */
function extractLanguage(className?: string): string {
  if (!className) return '';
  const match = className.match(/language-(\w+)/);
  return match ? match[1] : '';
}

// ─── Code Block ────────────────────────────────────────────────────
const CodeBlock: React.FC<{ className?: string; children: React.ReactNode }> = ({ className, children }) => {
  const language = extractLanguage(className);
  const code = extractCodeText(children).replace(/\n$/, '');
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <div className="code-block">
      <div className="code-block-header">
        <div className="code-block-lang">
          <span className="code-block-lang-icon">⚡</span>
          <span>{language || 'code'}</span>
        </div>
        <button
          type="button"
          className={`code-block-copy-btn ${copied ? 'copied' : ''}`}
          onClick={handleCopy}
          title="코드 복사"
        >
          {copied ? '✓ 복사됨' : '📋 복사'}
        </button>
      </div>
      <pre>
        {/*
         * CR-09: rehype-highlight가 만든 토큰 span(hljs-keyword 등)을 그대로 렌더한다.
         * 이전에는 평문(code)으로 치환해 토큰 색이 사라졌고, 로컬 번들로 가져온
         * tokyo-night-dark 테마는 기저 색만 칠할 수 있었다. span은 이미
         * rehype-sanitize의 `span: ['className', ...]` 스키마를 통과한 노드다.
         */}
        <code className={className}>{trimTrailingNewline(children)}</code>
      </pre>
    </div>
  );
};

const InlineCode: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <code className="inline-code">{children}</code>
);

// ─── Message Action Buttons ─────────────────────────────────────────
const MessageActions: React.FC<{ content: string }> = ({ content }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyAll = useCallback(() => {
    const clean = content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
    navigator.clipboard.writeText(clean).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  return (
    <div className="message-actions">
      <button
        type="button"
        className={`msg-action-btn ${copied ? 'copied' : ''}`}
        onClick={handleCopyAll}
        title="전체 응답 복사"
      >
        {copied ? '✓ 복사 완료' : '📋 복사'}
      </button>
    </div>
  );
};

function ChatMessageComponent({ message }: Props) {
  const { role, content } = message;
  const handleBubbleClick = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target instanceof Element
      ? event.target.closest<HTMLElement>('[data-agk-action]')
      : null;
    if (!target || !event.currentTarget.contains(target)) return;

    const action = target.dataset.agkAction;
    if (action === 'approval') {
      const text = target.dataset.response;
      if (text) {
        window.dispatchEvent(new CustomEvent('agk:approval-response', { detail: { text } }));
      }
      return;
    }

    if (action === 'preview') {
      const filePath = target.dataset.path;
      const fileName = target.dataset.name;
      if (filePath && fileName) {
        void window.previewArtifact?.(filePath, fileName);
      }
    }
  }, []);

  const handleBubbleKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const target = event.target instanceof Element
      ? event.target.closest<HTMLElement>('[data-agk-action]')
      : null;
    if (target && !(target instanceof HTMLButtonElement)) target.click();
  }, []);

  if (!content && role === 'assistant') return null;
  if (!content) return null;

  const avatar = role === 'user' ? '👤' : '🤖';

  const displayContent = role === 'assistant'
    ? preprocessContent(sanitizeMarkdown(content))
    : content;

  return (
    <div className={`message ${role}`}>
      <div className="avatar">{avatar}</div>
      <div
        className={`bubble glass-panel ${role === 'assistant' ? 'antigravity-assistant-bubble' : 'antigravity-user-bubble'}`}
        role={role === 'assistant' ? 'group' : undefined}
        onClick={role === 'assistant' ? handleBubbleClick : undefined}
        onKeyDown={role === 'assistant' ? handleBubbleKeyDown : undefined}
      >
        {role === 'assistant' && (
          <div className="antigravity-assistant-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', flexWrap: 'wrap', gap: 6 }}>
            <div className="assistant-identity-badge">
              <span className="assistant-spark">✦</span>
              <span className="assistant-identity-name">Ssak-Ai</span>
            </div>
            {message.agentMeta && (
              <div className="assistant-agent-meta" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '11px', opacity: 0.85 }}>
                <span className="badge badge-mode" style={{ background: 'rgba(255,255,255,0.08)', padding: '2px 6px', borderRadius: 4 }}>
                  ⚡ {message.agentMeta.mode || 'adaptive'}
                </span>
                {message.agentMeta.used_web && (
                  <span className="badge badge-web" title="Ssak-Search 웹 검색 참조" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', padding: '2px 6px', borderRadius: 4 }}>
                    🌐 web
                  </span>
                )}
                {message.agentMeta.used_graphify && (
                  <span className="badge badge-graphify" title="Graphify 코드베이스 하이브리드 검색" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', padding: '2px 6px', borderRadius: 4 }}>
                    🗺️ graphify
                  </span>
                )}
                {message.agentMeta.passed !== null && message.agentMeta.passed !== undefined && (
                  <span className={`badge ${message.agentMeta.passed ? 'badge-pass' : 'badge-fail'}`} style={{ background: message.agentMeta.passed ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)', color: message.agentMeta.passed ? '#4ade80' : '#f87171', padding: '2px 6px', borderRadius: 4 }}>
                    {message.agentMeta.passed ? '✅ passed' : '❌ failed'}
                  </span>
                )}
                {message.agentMeta.steps !== undefined && (
                  <span style={{ color: 'var(--text-muted, #888)' }}>
                    {message.agentMeta.steps} steps ({message.agentMeta.total_seconds?.toFixed(1) ?? '0.0'}s)
                  </span>
                )}
              </div>
            )}
          </div>
        )}
        {role === 'user' ? (
          <span className="user-message-text">{content}</span>
        ) : (
          <div className="antigravity-markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              rehypePlugins={[rehypeHighlight, rehypeRaw, [rehypeSanitize, markdownSanitizeSchema]]}
              components={{
                table({ children }) {
                  return (
                    <div className="agk-table-container">
                      <table className="agk-markdown-table">{children}</table>
                    </div>
                  );
                },
                code({ className, children }) {
                  const isInline = extractLanguage(className) === '' && !className?.includes('hljs');
                  if (isInline) {
                    return <InlineCode>{children}</InlineCode>;
                  }
                  const lang = extractLanguage(className);
                  const code = extractCodeText(children).replace(/\n$/, '');

                  // Mermaid diagram
                  if (lang === 'mermaid') {
                    return <MermaidDiagram code={code} />;
                  }

                  // Carousel slides (slides separated by <!-- slide -->)
                  if (lang === 'carousel') {
                    const slides = code.split(/<!--\s*slide\s*-->/).filter(Boolean).map(s => s.trim());
                    return <CarouselView slides={slides} />;
                  }

                  return <CodeBlock className={className}>{children}</CodeBlock>;
                },
                blockquote({ children }) {
                  return <GitHubAlert>{children}</GitHubAlert>;
                },
                pre({ children }) {
                  return <>{children}</>;
                },
                a({ href, children }) {
                  return (
                    <a href={href} target="_blank" rel="noopener noreferrer" className="agk-markdown-link">
                      {children}
                    </a>
                  );
                },
              }}
            >
              {displayContent}
            </ReactMarkdown>
          </div>
        )}
        {role === 'assistant' && content && (
          <MessageActions content={content} />
        )}
      </div>
    </div>
  );
}

/**
 * Custom comparator: only re-render if the message content/role/id actually changed.
 * This prevents ALL chat messages from re-rendering when a new message is added.
 */
export function chatMessageAreEqual(prevProps: Props, nextProps: Props): boolean {
  const a = prevProps.message;
  const b = nextProps.message;
  if (a.id !== b.id) return false;
  if (a.role !== b.role) return false;
  if (a.content !== b.content) return false;
  return true;
}

const ChatMessage = React.memo(ChatMessageComponent, chatMessageAreEqual);
ChatMessage.displayName = 'ChatMessage';

export default ChatMessage;
