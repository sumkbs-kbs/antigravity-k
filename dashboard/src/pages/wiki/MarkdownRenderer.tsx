/**
 * MarkdownRenderer — Simple Markdown → HTML renderer
 * ====================================================
 * Extracted from WikiPage.tsx. Converts markdown text to HTML
 * using regex-based transformations.
 */

export function renderMarkdown(md: string): string {
  if (!md) return '<p style="color:var(--text-muted);">내용이 없습니다.</p>';
  let html = md
    .replace(/^#### (.+)$/gm, '<h4 class="md-heading md-h4">$1</h4>')
    .replace(/^### (.+)$/gm, '<h3 class="md-heading md-h3">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="md-heading md-h2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="md-heading md-h1">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="md-link" target="_blank">$1</a>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^---$/gm, '<hr class="md-hr">')
    .replace(/\n\n/g, '</p><p class="md-p">')
    .replace(/\n/g, '<br>');
  html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul class="md-list">$1</ul>');
  return `<div class="md-p">${html}</div>`;
}
