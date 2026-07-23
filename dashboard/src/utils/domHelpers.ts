/**
 * DOM Helper utilities
 * =====================
 * Shared DOM helper functions used across multiple components.
 */

/**
 * Check if a Monaco Editor element is the active/focused element.
 * Used by CommandPalette, App keyboard shortcuts, and inline edit to
 * avoid conflicting with Monaco's own keyboard handlers.
 */
export function isMonacoFocused(): boolean {
  const active = document.activeElement;
  if (!active) return false;
  // Monaco editor content uses .monaco-editor and contenteditable / textarea within
  return !!active.closest?.('.monaco-editor') ||
         !!active.closest?.('.monaco-inputbox') ||
         active.className?.includes?.('monaco') ||
         ((active as HTMLElement)?.role === 'textbox' &&
          active.closest?.('.monaco-editor') !== null);
}
