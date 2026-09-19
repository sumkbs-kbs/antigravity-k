import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { WikiDocument } from '../../stores/wikiStore';
import ContentPanel from './ContentPanel';

const actions = {
  onEdit: vi.fn(),
  onSave: vi.fn(),
  onCancel: vi.fn(),
  onChatRef: vi.fn(),
  onEditContentChange: vi.fn(),
};

function renderDocument(content: string): HTMLElement {
  const wikiDocument: WikiDocument = { path: 'security.md', content, metadata: {} };
  render(
    <ContentPanel
      currentDoc={wikiDocument}
      isEditing={false}
      editContent=""
      {...actions}
    />,
  );
  const body = document.getElementById('wiki-body');
  if (!(body instanceof HTMLElement)) throw new TypeError('Wiki body is not an element');
  return body;
}

describe('ContentPanel Markdown security', () => {
  it('renders valid headings, lists, code, tables, links, and Korean text', () => {
    const body = renderDocument([
      '# 안녕하세요',
      '',
      '- 항목 하나',
      '- 항목 둘',
      '',
      '`inline code`와 [safe link](https://example.com/a?b=1#c)를 지원합니다.',
      '',
      '|열 하나|열 둘|',
      '|---|---|',
      '|값 1|값 2|',
      '',
      '```typescript',
      'const value = "safe";',
      '```',
    ].join('\n'));

    expect(body.querySelector('h1')).toHaveTextContent('안녕하세요');
    expect(body.querySelectorAll('li')).toHaveLength(2);
    expect(body.querySelector('code.inline-code')).toHaveTextContent('inline code');
    const link = screen.getByRole('link', { name: 'safe link' });
    expect(link).toHaveAttribute('href', 'https://example.com/a?b=1#c');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noreferrer');
    expect(body.querySelector('table')).toHaveTextContent('값 1값 2');
    expect(body.querySelector('pre code')).toHaveTextContent('const value = "safe";');
  });

  it('keeps raw HTML inert and removes event handlers', () => {
    const body = renderDocument(
      '<h2 id="qa-injected">injected</h2><img src="x" onerror="window.__agkWikiXss = true">',
    );

    expect(body.querySelector('#qa-injected')).not.toBeInTheDocument();
    expect(body.querySelector('[onerror]')).not.toBeInTheDocument();
    expect(body.textContent).not.toContain('window.__agkWikiXss');
  });

  it('drops script, iframe, and SVG active HTML', () => {
    const body = renderDocument(
      '<script>window.__agkWikiXss = true</script><iframe src="https://example.com"></iframe><svg><script>alert(1)</script></svg>',
    );

    expect(body.querySelector('script')).not.toBeInTheDocument();
    expect(body.querySelector('iframe')).not.toBeInTheDocument();
    expect(body.querySelector('svg')).not.toBeInTheDocument();
    expect(window.__agkWikiXss).toBeUndefined();
  });

  it('blocks javascript and data URLs while preserving safe links', () => {
    const body = renderDocument(
      '[script](javascript:window.__agkWikiXss=true) [data](data:text/html,<script>alert(1)</script>) [safe](https://example.com)',
    );

    const safeLink = screen.getByRole('link', { name: 'safe' });
    expect(safeLink).toHaveAttribute('href', 'https://example.com');
    expect(body.querySelector('a[href^="javascript:"]')).not.toBeInTheDocument();
    expect(body.querySelector('a[href^="data:"]')).not.toBeInTheDocument();
  });

  it('does not allow malformed link syntax to break out into attributes', () => {
    const body = renderDocument('[label](https://example.com/ "onmouseover="alert(1))');

    expect(body.querySelector('[onmouseover]')).not.toBeInTheDocument();
    expect(body.querySelector('a[href*="onmouseover"]')).not.toBeInTheDocument();
  });
});

declare global {
  interface Window {
    __agkWikiXss?: boolean;
  }
}
