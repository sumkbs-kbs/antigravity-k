import React from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';

const wikiTagNames = [
  'a', 'blockquote', 'br', 'code', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'hr', 'li', 'ol', 'p', 'pre', 'span', 'strong', 'table', 'tbody', 'td',
  'th', 'thead', 'tr', 'ul',
] as const satisfies readonly string[];

const wikiSanitizeSchema = {
  ...defaultSchema,
  tagNames: [...wikiTagNames],
  attributes: {
    ...defaultSchema.attributes,
    a: [...(defaultSchema.attributes?.a ?? []), 'target', 'rel'],
    code: [...(defaultSchema.attributes?.code ?? []), 'className'],
    span: [...(defaultSchema.attributes?.span ?? []), 'className'],
  },
  protocols: {
    ...defaultSchema.protocols,
    href: [...(defaultSchema.protocols?.href ?? []), 'tel'],
    src: ['http', 'https'],
  },
} as const;

function safeWikiUrl(url: string): string {
  const transformed = defaultUrlTransform(url);
  if (!transformed) return '';
  const parsed = new URL(transformed, 'https://wiki.ssak-ai.invalid');
  const safeProtocols = new Set(['http:', 'https:', 'mailto:', 'tel:']);
  return safeProtocols.has(parsed.protocol) ? transformed : '';
}

export function WikiMarkdown({ content }: { readonly content: string }) {
  if (!content) {
    return <p style={{ color: 'var(--text-muted)' }}>내용이 없습니다.</p>;
  }

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight, [rehypeSanitize, wikiSanitizeSchema]]}
      skipHtml
      urlTransform={safeWikiUrl}
      components={{
        a({ children, href }) {
          return (
            <a className="md-link" href={href ?? ''} rel="noreferrer" target="_blank">
              {children}
            </a>
          );
        },
        code({ children, className }) {
          if (className) {
            return <code className={className}>{children}</code>;
          }
          return <code className="inline-code">{children}</code>;
        },
        h1({ children }) {
          return <h1 className="md-heading md-h1">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="md-heading md-h2">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="md-heading md-h3">{children}</h3>;
        },
        h4({ children }) {
          return <h4 className="md-heading md-h4">{children}</h4>;
        },
        hr() {
          return <hr className="md-hr" />;
        },
        table({ children }) {
          return <div className="md-table-wrap"><table>{children}</table></div>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
