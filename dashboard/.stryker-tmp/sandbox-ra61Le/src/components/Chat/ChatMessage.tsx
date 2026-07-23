/**
 * ChatMessage — Individual message bubble with rendering
 * Supports: agent badges, tool timeline, artifact preview, approval UI,
 * code syntax highlighting, markdown tables, copy actions,
 * GitHub Alerts, Mermaid diagrams, and Carousel slideshows.
 */
// @ts-nocheck


import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatMessage as ChatMessageType } from '../../stores/chatStore';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { preprocessContent } from '../../utils/formatContent';

interface Props {
  message: ChatMessageType;
}

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
    mermaid: any;
  }
}

const MermaidDiagram: React.FC<{ code: string }> = ({ code }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const renderId = useRef(`mermaid-${Math.random().toString(36).slice(2, 9)}`).current;

  useEffect(() => {
    if (!containerRef.current || !window.mermaid) {
      setError('Mermaid library not loaded');
      setLoading(false);
      return;
    }

    let cancelled = false;

    const render = async () => {
      try {
        if (!containerRef.current) return;
        containerRef.current.innerHTML = '';
        const { svg } = await window.mermaid.render(renderId, code);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e.message || 'Mermaid render failed');
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
              key={i}
              type="button"
              className={`carousel-dot ${i === current ? 'active' : ''}`}
              onClick={() => setCurrent(i)}
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
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight, rehypeRaw]}
        >
          {body}
        </ReactMarkdown>
      </div>
    </div>
  );
};

// ─── Code Block ────────────────────────────────────────────────────
const CodeBlock: React.FC<{ className?: string; children: React.ReactNode }> = ({ className, children }) => {
  const language = className?.replace('language-', '') || '';
  const code = String(children).replace(/\n$/, '');

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).catch(() => {});
  }, [code]);

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span>{language || 'code'}</span>
        <button className="code-block-copy-btn" onClick={handleCopy}>
          📋 복사
        </button>
      </div>
      <pre>
        <code className={className}>{code}</code>
      </pre>
    </div>
  );
};

const InlineCode: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <code className="inline-code">{children}</code>
);

// ─── Message Action Buttons ─────────────────────────────────────────
const MessageActions: React.FC<{ content: string }> = ({ content }) => {
  const handleCopyAll = useCallback(() => {
    navigator.clipboard.writeText(content).catch(() => {});
  }, [content]);

  return (
    <div className="message-actions">
      <button className="msg-action-btn" onClick={handleCopyAll}>
        📋 복사
      </button>
    </div>
  );
};

function ChatMessageComponent({ message }: Props) {
  const { role, content } = message;
  if (!content && role === 'assistant') return null;
  if (!content) return null;

  const avatar = role === 'user' ? '👤' : '🤖';

  // Preprocess assistant content for custom agent patterns
  const displayContent = role === 'assistant' ? preprocessContent(content) : content;

  return (
    <div className={`message ${role}`}>
      <div className="avatar">{avatar}</div>
      <div className="bubble glass-panel">
        {role === 'user' ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight, rehypeRaw]}
            components={{
              code({ className, children, ...props }) {
                const isInline = !className;
                if (isInline) {
                  return <InlineCode>{children}</InlineCode>;
                }
                const lang = className?.replace('language-', '') || '';
                const code = String(children).replace(/\n$/, '');

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
            }}
          >
            {displayContent}
          </ReactMarkdown>
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
function chatMessageAreEqual(prevProps: Props, nextProps: Props): boolean {
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
