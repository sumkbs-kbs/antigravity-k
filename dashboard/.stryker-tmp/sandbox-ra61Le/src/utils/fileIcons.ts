/**
 * File Icons — Shared file-to-icon mapping
 * ==========================================
 * Extracted from FileTree.tsx and SearchPanel.tsx to eliminate duplication.
 * Both components now import from this single source of truth.
 */
// @ts-nocheck


const ICON_MAP: Record<string, string> = {
  js: '🟨', ts: '🟦', tsx: '⚛️', jsx: '⚛️',
  py: '🐍', rs: '🦀', go: '🔵', java: '☕',
  html: '🌐', css: '🎨', scss: '🎨', json: '📋',
  md: '📝', yaml: '📋', yml: '📋', toml: '⚙️',
  sh: '💻', bash: '💻', zsh: '💻',
  sql: '🗃️', xml: '📄', svg: '🖼️',
  lock: '🔒', gitignore: '🙈',
};

/**
 * Returns an emoji icon for a given filename based on its extension.
 * Falls back to 📄 for unknown file types.
 */
export function getFileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return ICON_MAP[ext] || '📄';
}
