/**
 * formatContent — Preprocesses assistant markdown content
 * ======================================================
 * Converts custom agent patterns (badges, timelines, artifacts, etc.)
 * to HTML before ReactMarkdown rendering.
 *
 * Ported from Vanilla JS original (chat.js formatContent function).
 */

import DOMPurify from 'dompurify';

// ─── Agent Badge Definitions ────────────────────────────────────────
const AGENT_BADGES: Record<string, [string, string]> = {
  CEO: ['ceo', '🏢'],
  WORKER: ['worker', '👨‍💻'],
  ENG_MANAGER: ['eng', '🏗️'],
  QA: ['qa', '🔍'],
  DESIGNER: ['designer', '🎨'],
  ARCHITECT: ['architect', '🏗️'],
  PROPOSER: ['proposer', '💡'],
  CRITIC: ['critic', '⚖️'],
  ARBITER: ['arbiter', '🔨'],
  SELF: ['self', '💬'],
};

export function sanitizeMarkdown(text: string): string {
  if (!text) return text;

  const protectedSegments: string[] = [];
  const protectedText = text
    .replace(/```[\s\S]*?```|`[^`]+`/g, (segment) => {
      const token = `__AGK_PROTECTED_${protectedSegments.length}__`;
      protectedSegments.push(segment);
      return token;
    })
    .replace(/<\/?think>/gi, (tag) => {
      const token = `__AGK_PROTECTED_${protectedSegments.length}__`;
      protectedSegments.push(tag);
      return token;
    });

  let sanitized = DOMPurify.sanitize(protectedText, {
    USE_PROFILES: { html: true },
    FORBID_ATTR: ['style'],
  });
  protectedSegments.forEach((segment, index) => {
    sanitized = sanitized.replace(`__AGK_PROTECTED_${index}__`, segment);
  });
  return sanitized;
}

/**
 * Preprocess agent-specific markdown patterns into HTML
 * that react-markdown can render with rehype-raw.
 */
export function preprocessContent(text: string): string {
  if (!text) return text;

  // ── Step 1: Protect code blocks ──
  const codeBlocks: Array<{ lang: string; code: string }> = [];
  let processed = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_match, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push({ lang: lang || '', code });
    return `%%CODEBLOCK_${idx}%%`;
  });

  // ── Step 2: Protect inline code ──
  const inlineCodes: string[] = [];
  processed = processed.replace(/`([^`]+)`/g, (_match, code) => {
    const idx = inlineCodes.length;
    inlineCodes.push(code);
    return `%%INLINE_${idx}%%`;
  });

  // ── Step 2.5: Antigravity Thinking Process (DeepSeek / Qwen reasoning) ──
  // Completed <think>...</think>
  processed = processed.replace(/<think>([\s\S]*?)<\/think>/gi, (_match, thinkContent) => {
    const trimmed = thinkContent.trim();
    if (!trimmed) return '';
    return `\n\n<details class="antigravity-thought-box" open><summary class="thought-summary"><div class="thought-summary-left"><span class="thought-icon">🧠</span><span class="thought-title">생각 과정 (Thinking Process)</span></div><span class="thought-status-badge">완료</span></summary><div class="thought-body">${escapeHTML(trimmed)}</div></details>\n\n`;
  });

  // Streaming unclosed <think>...
  processed = processed.replace(/<think>([\s\S]*)$/gi, (_match, thinkContent) => {
    const trimmed = thinkContent.trim();
    if (!trimmed) return '';
    return `\n\n<details class="antigravity-thought-box" open><summary class="thought-summary"><div class="thought-summary-left"><span class="thought-icon">🧠</span><span class="thought-title">생각 중... (Thinking...)</span></div><span class="thought-status-badge streaming">사고 중</span></summary><div class="thought-body">${escapeHTML(trimmed)}</div></details>\n\n`;
  });

  // ── Step 2.6: GitHub-Style Alerts — > [!NOTE] / [!TIP] / [!IMPORTANT] / [!WARNING] / [!CAUTION] ──
  // Convert markdown blockquote alerts into styled HTML blockquotes
  const ALERT_TYPES: Record<string, [string, string]> = {
    NOTE: ['note', 'ℹ️'],
    TIP: ['tip', '💡'],
    IMPORTANT: ['important', '❗'],
    WARNING: ['warning', '⚠️'],
    CAUTION: ['caution', '🚨'],
  };
  for (const [typeName, [cssClass, icon]] of Object.entries(ALERT_TYPES)) {
    // Match: > [!TYPE]\n> content... (multiple lines starting with >)
    const alertRegex = new RegExp(
      `> \\[!${typeName}\\]\n((?:> [^\n]*\n?)+)`,
      'gi'
    );
    processed = processed.replace(alertRegex, (_match: string, contentBlock: string) => {
      // Extract content lines, strip the "> " prefix
      const contentLines = contentBlock
        .split('\n')
        .map((line: string) => line.replace(/^>\s?/, ''));
      const bodyHtml = contentLines
        .filter((l: string) => l.trim())
        .map((l: string) => `<p>${escapeHTML(l)}</p>`)
        .join('\n');

      return (
        `<blockquote class="github-alert-${cssClass}">` +
        `<div class="github-alert-header"><span class="alert-icon">${icon}</span><span>${typeName.charAt(0) + typeName.slice(1).toLowerCase()}</span></div>` +
        `${bodyHtml}` +
        `</blockquote>`
      );
    });
  }

  // ── Step 3: Agent Badges — **CEO** → HTML badge ──
  for (const [name, [cls, emoji]] of Object.entries(AGENT_BADGES)) {
    const re = new RegExp(`\\*\\*\\[?${name}\\]?\\*\\*`, 'g');
    processed = processed.replace(re, `<span class="agent-badge ${cls}">${emoji} ${name}</span>`);
  }

  // ── Step 4: Agent Timeline / Tool Visualizations ──

  // **도구 실행** (step X/Y): tool_name
  processed = processed.replace(
    /\*\*도구 실행\*\*\s*\(step\s*(\d+)\/(\d+)\):\s*(%%INLINE_\d+%%)/g,
    (_match, step, total, toolPlaceholder) => {
      const idx = parseInt(toolPlaceholder.match(/%%INLINE_(\d+)%%/)?.[1] || '0');
      const toolName = inlineCodes[idx] || toolPlaceholder;
      return `<div class="tool-timeline-badge antigravity-tool-card start"><div class="tool-card-left"><span class="tool-card-icon">⚡</span> <span class="tool-card-title">Executing Tool <b>${escapeHTML(toolName)}</b></span> <span class="step-info">(Step ${step}/${total})</span></div><span class="tool-card-status success">✓ 완료</span></div>`;
    }
  );

  // Tool Call: tool_name or call:default_api:tool_name
  processed = processed.replace(
    /(?:call:default_api:|Tool Call:\s*)([a-zA-Z0-9_]+)/g,
    (_match, toolName) => {
      return `<div class="tool-timeline-badge antigravity-tool-card start"><div class="tool-card-left"><span class="tool-card-icon">⚡</span> <span class="tool-card-title">Tool: <b>${escapeHTML(toolName)}</b></span></div><span class="tool-card-status success">✓ 완료</span></div>`;
    }
  );

  // 🐍 **[Ouroboros Guard]**
  processed = processed.replace(
    /🐍 \*\*\[Ouroboros Guard\]\*\*(.*)/g,
    (_match, detail) => `<div class="tool-timeline-badge warning"><span class="icon">🐍</span> <span class="text"><b>Ouroboros Guard:</b>${escapeHTML(detail)}</span></div>`
  );

  // ⚠️ **[Step Limit]**
  processed = processed.replace(
    /⚠️ \*\*\[Step Limit\]\*\*(.*)/g,
    (_match, detail) => `<div class="tool-timeline-badge error"><span class="icon">🛑</span> <span class="text"><b>Step Limit:</b>${escapeHTML(detail)}</span></div>`
  );

  // ⚠️ **[TOOL CALL PARSE ERROR]**
  processed = processed.replace(
    /⚠️ \*\*\[TOOL CALL PARSE ERROR\](.*)\*\*/g,
    (_match, detail) => `<div class="tool-timeline-badge error"><span class="icon">⚠️</span> <span class="text"><b>Parse Error:</b>${escapeHTML(detail)}</span></div>`
  );

  // ── Step 4.5: Markdown List & Callout Normalization ──
  // Convert unicode bullets (•, ●, ◦, ▪, etc.) at line start to standard markdown list syntax "- "
  processed = processed.replace(/^[ \t]*[•●◦▪▫◆◇][ \t]*/gm, '- ');

  // Ensure blank line before list start if preceded by a regular non-list paragraph line
  processed = processed.replace(/^([ \t]*[^\n\-*+\d\s<#>][^\n]*)\n([ \t]*(?:[-*+]|\d+\.)\s)/gm, '$1\n\n$2');

  // Ensure blank line after list item if followed by regular non-list paragraph line
  processed = processed.replace(/^([ \t]*(?:[-*+]|\d+\.)[^\n]+)\n([ \t]*[^\n\-*+\d\s<#>])/gm, '$1\n\n$2');

  // Normalize tip callouts: 💡 팁: ... or 💡 Tip: ...
  processed = processed.replace(
    /^[ \t]*💡\s*(?:\*\*)?(?:팁|Tip|TIP):?(?:\*\*)?\s*(.+)$/gm,
    (_match, tipText) => {
      const escaped = escapeHTML(tipText.trim());
      const linkified = escaped.replace(
        /(https?:\/\/[^\s<)]+)/g,
        '<a href="$1" target="_blank" rel="noopener noreferrer" style="color:var(--accent-color);text-decoration:underline;">$1</a>'
      );
      return `\n\n<div class="tip-callout"><span class="tip-callout-icon">💡</span><div class="tip-callout-body"><span class="tip-callout-title">팁:</span>${linkified}</div></div>\n\n`;
    }
  );

  // 📊 **[Token Usage]**
  processed = processed.replace(
    /📊 (?:Tokens Used|\*\*\[Token Usage\]\*\*):?\s*In:\s*([\d,]+)(?:\s*tokens)?\s*\|\s*Out:\s*([\d,]+)(?:\s*tokens)?/gi,
    '<div class="tool-timeline-badge token"><span class="icon">📊</span> <span class="text"><b>Tokens Used:</b> <span class="token-val">In: $1</span> | <span class="token-val">Out: $2</span></span></div>'
  );

  // 🔄 **[Quality Retry]**
  processed = processed.replace(
    /🔄 \*\*품질 미달 \(([\d]+)%\)\*\* — 자동 개선 중\.\.\./g,
    '<div class="tool-timeline-badge warning"><span class="icon">🔄</span> <span class="text"><b>Quality Retry:</b> Score $1% - Auto improving...</span></div>'
  );

  // ── Step 5: Approval Required UI ──
  processed = processed.replace(
    /\[APPROVAL REQUIRED\]\s*([^<]*)(?:<br>|\n)?[^\n]*Wait for their 'Yes' before retrying\.?/g,
    (_match, msg) => {
      const trimmedMsg = escapeHTML(msg.trim());
      return `<div class="tool-timeline-badge approval-box" style="border: 2px solid var(--accent-color); background: rgba(0, 122, 204, 0.1); padding: 12px; margin-top: 8px; border-radius: 8px;">
        <div style="display:flex; align-items:center; margin-bottom: 8px;">
          <span style="font-size:20px; margin-right:12px;">✋</span>
          <div style="display:flex; flex-direction:column;">
            <span style="font-weight:bold; color:var(--text-primary); font-size:14px;">APPROVAL REQUIRED</span>
            <span style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${trimmedMsg}</span>
          </div>
        </div>          <div style="display:flex; gap:8px; margin-top:12px;">
            <button class="glow-btn" data-agk-action="approval" data-response="승인합니다" style="flex:1; background:var(--accent-color); border:none; border-radius:4px; padding:8px; color:#fff; cursor:pointer;">승인 (Approve)</button>
            <button data-agk-action="approval" data-response="거절합니다" style="flex:1; background:transparent; border:1px solid var(--glass-border); border-radius:4px; padding:8px; color:var(--text-primary); cursor:pointer;">거절 (Reject)</button>
          </div>
      </div>`;
    }
  );

  // ── Step 6: Artifact Generated ──
  processed = processed.replace(
    /\[ARTIFACT GENERATED: (.*?) \(Type: (.*?)\)\]\nSuccessfully saved to ([^\n]+?)(?:\.)?(?=\n|$)/g,
    (_match, fname, type, path) => {
      const safePath = escapeHTML(path);
      const safeName = escapeHTML(fname);
      const btnHtml = (type === 'html' || type === 'react')
        ? `<button class="preview-btn" data-agk-action="preview" data-path="${safePath}" data-name="${safeName}" style="margin-left:auto; background:var(--accent-color); font-size:11px; padding: 4px 8px; border:none; border-radius:4px; color:#fff; cursor:pointer;">View Preview</button>`
        : '';
      return `<div class="tool-timeline-badge artifact" style="border-left: 3px solid #10b981; background: rgba(16, 185, 129, 0.1); width:100%; display:flex; align-items:center;">
        <span style="margin-right:8px;">🎨</span>
        <div style="display:flex; flex-direction:column;">
          <span style="font-weight:bold;">Artifact: ${safeName}</span>
          <span style="font-size:11px; color:#aaa;">Saved to project</span>
        </div>
        ${btnHtml}
      </div>`;
    }
  );

  // ── Step 7: Restore protected blocks ──
  // Restore inline code
  processed = processed.replace(/%%INLINE_(\d+)%%/g, (_match, idx) => {
    return `\`${inlineCodes[parseInt(idx)] || ''}\``;
  });

  // Restore code blocks
  processed = processed.replace(/%%CODEBLOCK_(\d+)%%/g, (_match, idx) => {
    const block = codeBlocks[parseInt(idx)];
    if (!block) return '';
    return '```' + block.lang + '\n' + block.code + '```';
  });

  return processed;
}

/**
 * Escape HTML special characters for user messages.
 */
export function escapeHTML(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/'/g, '&#39;')
    .replace(/"/g, '&quot;');
}
