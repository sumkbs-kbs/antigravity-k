/**
 * CommandPalette — Cmd+K omnibox
 * ===============================
 * Ported from Vanilla JS. Provides search + actions across all pages.
 * Cmd+K is intercepted globally but suppressed when Monaco Editor is focused.
 *
 * Note: The global Cmd+K keyboard hook has been moved to
 * ``src/hooks/useGlobalCommandPalette.ts`` to allow React.lazy on this
 * component without losing the global shortcut.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent as ReactMouseEvent } from 'react';

import { CommandIcon } from '../../features/command-palette/CommandIcon';
import {
  BUILTIN_COMMANDS,
  CommandSearchError,
  filterPaletteCommands,
  searchNoteCommands,
} from '../../features/command-palette/commandRegistry';
import type { PaletteCommand } from '../../features/command-palette/commandRegistry';
import { usePluginCommands } from '../../plugin/PluginManager';
import { useUiStore } from '../../stores/uiStore';

const CommandPalette: React.FC = () => {
  const { addToast, commandPaletteVisible, setCommandPaletteVisible } = useUiStore();
  const pluginCommands = usePluginCommands();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<readonly PaletteCommand[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchRequestRef = useRef(0);
  const availableCommands = useMemo<readonly PaletteCommand[]>(() => [
    ...BUILTIN_COMMANDS,
    ...pluginCommands.map((command) => ({
      id: `plugin:${command.id}`,
      title: command.label,
      subtitle: command.category ?? 'Plugin',
      icon: 'plugin',
      keywords: [command.id, command.category ?? 'plugin'],
      disabled: false,
      execute: command.execute,
    } satisfies PaletteCommand)),
  ], [pluginCommands]);
  const hideAfterAction = useCallback(() => {
    searchRequestRef.current += 1;
    setCommandPaletteVisible(false);
    setQuery('');
    setSelectedIndex(0);
  }, [setCommandPaletteVisible]);

  const getLocalMatches = useCallback(
    (value: string): readonly PaletteCommand[] => filterPaletteCommands(availableCommands, value),
    [availableCommands],
  );

  // Show results on open / query change
  useEffect(() => {
    if (!commandPaletteVisible) return;
    setResults(getLocalMatches(query));
    setSelectedIndex(0);
  }, [commandPaletteVisible, query, getLocalMatches]);

  // Focus input when opened
  useEffect(() => {
    if (commandPaletteVisible) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [commandPaletteVisible]);

  const performSearch = useCallback(async (value: string) => {
    if (value.trim().length === 0) {
      setResults(getLocalMatches(''));
      return;
    }
    const requestId = searchRequestRef.current + 1;
    searchRequestRef.current = requestId;
    const local = getLocalMatches(value);
    try {
      const noteCommands = await searchNoteCommands(value);
      if (searchRequestRef.current !== requestId) return;
      setResults([...local, ...noteCommands]);
      setSelectedIndex(0);
    } catch (error) {
      if (!(error instanceof CommandSearchError)) throw error;
      if (searchRequestRef.current !== requestId) return;
      setResults(local.length > 0 ? local : [{
        id: 'search-error',
        title: 'Error searching notes',
        subtitle: 'Search unavailable',
        icon: 'warning',
        keywords: [],
        disabled: true,
        execute: () => undefined,
      }]);
    }
  }, [getLocalMatches]);

  // Debounced search
  const handleInput = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setResults(getLocalMatches(val));
    setSelectedIndex(0);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => performSearch(val), 300);
  }, [getLocalMatches, performSearch]);

  const reportExecutionError = useCallback((error: unknown): void => {
    if (error instanceof Error) {
      addToast(`Command failed: ${error.message}`, 'error');
      return;
    }
    throw error;
  }, [addToast]);

  const executeCommand = useCallback((command: PaletteCommand): void => {
    if (command.disabled) return;
    try {
      void Promise.resolve(command.execute()).catch(reportExecutionError);
      hideAfterAction();
    } catch (error) {
      reportExecutionError(error);
    }
  }, [hideAfterAction, reportExecutionError]);

  const handleKeyDown = useCallback((e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((index) => results.length === 0 ? 0 : Math.min(index + 1, results.length - 1));
    }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIndex(i => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      const command = results[selectedIndex];
      if (command !== undefined) executeCommand(command);
    }
  }, [executeCommand, results, selectedIndex]);

  const handleOverlayClick = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) hideAfterAction();
  }, [hideAfterAction]);

  // Listen for escape key to close
  useEffect(() => {
    if (!commandPaletteVisible) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') hideAfterAction();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [commandPaletteVisible, hideAfterAction]);

  useEffect(() => () => {
    if (searchTimeoutRef.current !== null) clearTimeout(searchTimeoutRef.current);
  }, []);

  if (!commandPaletteVisible) return null;

  return (
    <div className="command-palette-overlay" style={{ display: 'flex' }} onClick={handleOverlayClick}>
      <div className="command-palette" role="dialog" aria-label="명령 팔레트">
        <div className="cmd-header">
          <span className="cmd-icon"><CommandIcon icon="search" /></span>
          <input
            ref={inputRef}
            type="text"
            className="cmd-input"
            placeholder="Search notes or run commands... (Use ↑↓ to navigate)"
            value={query}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            autoComplete="off"
            spellCheck={false}
            aria-label="검색어 입력"
            role="combobox"
            aria-autocomplete="list"
            aria-controls="cmd-results"
            aria-expanded="true"
            aria-activedescendant={results[selectedIndex] === undefined ? undefined : `cmd-option-${results[selectedIndex].id}`}
          />
          <span className="cmd-shortcut" aria-label="닫기">ESC</span>
        </div>
        <div className="cmd-results" id="cmd-results" role="listbox" aria-label="검색 결과">
          {results.length === 0 ? (
            <div className="cmd-empty">No results found</div>
          ) : (
            results.map((cmd, index) => (
              <button
                key={cmd.id}
                id={`cmd-option-${cmd.id}`}
                type="button"
                className={`cmd-item ${index === selectedIndex ? 'selected' : ''}`}
                role="option"
                aria-selected={index === selectedIndex}
                disabled={cmd.disabled}
                onClick={() => executeCommand(cmd)}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <span className="cmd-item-icon"><CommandIcon icon={cmd.icon} /></span>
                <span className="cmd-item-title">{cmd.title}</span>
                {cmd.subtitle !== null && <span className="cmd-item-subtitle">{cmd.subtitle}</span>}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default CommandPalette;
