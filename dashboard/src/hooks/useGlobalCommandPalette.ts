/**
 * useGlobalCommandPalette — Cmd+K global keyboard shortcut hook
 * ==============================================================
 * Extracted from CommandPalette.tsx to allow React.lazy on the
 * CommandPalette component without losing the global shortcut.
 * This hook is tiny (~1 kB) so it's fine as a static import.
 */

import { useEffect } from 'react';
import { useUiStore } from '../stores/uiStore';
import { isMonacoFocused } from '../utils/domHelpers';

/**
 * Global Cmd+K handler with Monaco conflict prevention.
 * Place once in the app root (AppContent).
 */
export function useGlobalCommandPalette() {
  const { commandPaletteVisible, setCommandPaletteVisible } = useUiStore();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Cmd+K / Ctrl+K — but NOT when Monaco editor is focused
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        if (isMonacoFocused()) return; // Let Monaco handle its own Cmd+K
        e.preventDefault();
        e.stopPropagation();
        setCommandPaletteVisible(!commandPaletteVisible);
      }
      // Escape to close
      if (e.key === 'Escape' && commandPaletteVisible) {
        setCommandPaletteVisible(false);
      }
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [commandPaletteVisible, setCommandPaletteVisible]);
}
