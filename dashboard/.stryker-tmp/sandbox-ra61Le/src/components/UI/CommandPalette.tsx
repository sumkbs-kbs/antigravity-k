/**
 * CommandPalette — Cmd+K omnibox
 * ===============================
 * Ported from Vanilla JS. Provides search + actions across all pages.
 * Cmd+K is intercepted globally but suppressed when Monaco Editor is focused.
 */
// @ts-nocheck


import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';

interface Command {
  id: string;
  title: string;
  icon: string;
  subtitle?: string;
  action: () => void;
}

const AVAILABLE_COMMANDS: Command[] = [
  { id: 'search', title: 'Search Notes', icon: '🔍', action: () => {} },
  { id: 'new_note', title: 'Create New Note', icon: '📝', action: () => {
    const { navigate: nav } = useUiStore.getState() as any;
    window.dispatchEvent(new CustomEvent('agk:open-wiki-new'));
  }},
  { id: 'chat', title: 'Open AI Chat', icon: '💬', action: () => {
    window.dispatchEvent(new CustomEvent('agk:navigate', { detail: '/chat' }));
  }},
  { id: 'goal', title: 'Autonomous Goal (/goal)', icon: '🎯', action: () => {
    window.dispatchEvent(new CustomEvent('agk:chat-slash', { detail: { text: '/goal ' } }));
  }},
  { id: 'agentic', title: 'Agentic Upgrade Radar (/agentic)', icon: '🧭', action: () => {
    window.dispatchEvent(new CustomEvent('agk:chat-slash', { detail: { text: '/agentic ' } }));
  }},
  { id: 'mcp', title: 'MCP Upgrade Radar (/mcp)', icon: '🔌', action: () => {
    window.dispatchEvent(new CustomEvent('agk:chat-slash', { detail: { text: '/mcp ' } }));
  }},
  { id: 'capabilities', title: 'Autonomous Capabilities (/capabilities)', icon: '🧠', action: () => {
    window.dispatchEvent(new CustomEvent('agk:chat-slash', { detail: { text: '/capabilities ' } }));
  }},
  { id: 'self', title: 'Self Capability Report (/self)', icon: '🪪', action: () => {
    window.dispatchEvent(new CustomEvent('agk:chat-slash', { detail: { text: '/self' } }));
  }},
  { id: 'codex', title: 'Codex Capability Transfer (/codex)', icon: '⚡', action: () => {
    window.dispatchEvent(new CustomEvent('agk:chat-slash', { detail: { text: '/codex ' } }));
  }},
  { id: 'benchmark', title: 'Collective Benchmark Report (/benchmark)', icon: '📊', action: () => {
    window.dispatchEvent(new CustomEvent('agk:chat-slash', { detail: { text: '/benchmark report' } }));
  }},
  { id: 'settings', title: 'Preferences', icon: '⚙️', action: () => {
    window.dispatchEvent(new CustomEvent('agk:navigate', { detail: '/settings' }));
  }},
  { id: 'sync', title: 'Sync Vault (Git)', icon: '🔄', action: () => {
    const { addToast } = useUiStore.getState();
    addToast('🔄 Vault 동기화 중...', 'info');
    fetch('/api/vault/sync', { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        if (d.ok) addToast(`✅ Vault 동기화 완료 (commit: ${(d.commit || '').substring(0, 7) || 'N/A'})`, 'success');
        else addToast('❌ Vault 동기화 실패', 'error');
      })
      .catch((e: any) => addToast(`❌ Vault 동기화 오류: ${e.message}`, 'error'));
  }},
  { id: 'selftest', title: 'Self-Test', icon: '🧪', action: () => {
    useUiStore.getState().addToast('🧪 Self-test triggered', 'info');
  }},
  { id: 'tdd_loop', title: 'Test-Driven Code Generation (Cmd+Shift+D)', icon: '🧪', action: () => {
    useUiStore.getState().addToast('🧪 TDD 루프 생성 중...', 'info');
  }},
];

import { isMonacoFocused } from '../../utils/domHelpers';

const CommandPalette: React.FC = () => {
  const navigate = useNavigate();
  const { commandPaletteVisible, setCommandPaletteVisible } = useUiStore();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Command[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hideAfterAction = useCallback(() => {
    setCommandPaletteVisible(false);
    setQuery('');
    setSelectedIndex(0);
  }, [setCommandPaletteVisible]);

  // Navigate helper using React Router
  const doNavigate = useCallback((path: string) => {
    hideAfterAction();
    setTimeout(() => navigate(path), 50);
  }, [navigate, hideAfterAction]);

  // Filter commands locally
  const getLocalMatches = useCallback((q: string): Command[] => {
    const norm = q.toLowerCase();
    return AVAILABLE_COMMANDS.filter(cmd =>
      cmd.title.toLowerCase().includes(norm) || cmd.id.includes(norm)
    );
  }, []);

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

  // Perform web search for notes
  const performSearch = useCallback(async (q: string) => {
    if (!q) {
      setResults(getLocalMatches(''));
      return;
    }
    const local = getLocalMatches(q);
    try {
      const res = await fetch(`/v1/notes/search?q=${encodeURIComponent(q)}`);
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();
      const apiCommands: Command[] = [];

      if (data.semantic_results?.length) {
        data.semantic_results.forEach((r: any) => {
          apiCommands.push({
            id: 'rag_res', title: (r.text || '').substring(0, 40) + '...',
            subtitle: 'Semantic Match', icon: '🧠',
            action: () => {
              const path = r.metadata?.source || r.id;
              hideAfterAction();
              setTimeout(() => window.dispatchEvent(new CustomEvent('agk:open-wiki-note', { detail: path })), 150);
            },
          });
        });
      }
      if (data.keyword_results?.length) {
        data.keyword_results.forEach((path: string) => {
          apiCommands.push({
            id: 'kw_res', title: path,
            subtitle: 'Keyword Match', icon: '📄',
            action: () => {
              hideAfterAction();
              setTimeout(() => window.dispatchEvent(new CustomEvent('agk:open-wiki-note', { detail: path })), 150);
            },
          });
        });
      }
      setResults([...local, ...apiCommands]);
      setSelectedIndex(0);
    } catch {
      setResults(local.length > 0 ? local : [{ id: 'error', title: 'Error searching notes', icon: '⚠️', action: () => {} }]);
    }
  }, [getLocalMatches, hideAfterAction]);

  // Debounced search
  const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setResults(getLocalMatches(val));
    setSelectedIndex(0);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => performSearch(val), 300);
  }, [getLocalMatches, performSearch]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex(i => Math.min(i + 1, results.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIndex(i => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      const cmd = results[selectedIndex];
      if (cmd) { cmd.action(); hideAfterAction(); }
    }
  }, [results, selectedIndex, hideAfterAction]);

  const handleOverlayClick = useCallback((e: React.MouseEvent) => {
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

  if (!commandPaletteVisible) return null;

  return (
    <div className="command-palette-overlay" style={{ display: 'flex' }} onClick={handleOverlayClick}>
      <div className="command-palette" role="dialog" aria-label="명령 팔레트">
        <div className="cmd-header">
          <span className="cmd-icon" aria-hidden="true">🔍</span>
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
          />
          <span className="cmd-shortcut" aria-label="닫기">ESC</span>
        </div>
        <div className="cmd-results" id="cmd-results" role="listbox" aria-label="검색 결과">
          {results.length === 0 ? (
            <div className="cmd-empty">No results found</div>
          ) : (
            results.map((cmd, index) => (
              <div
                key={cmd.id + index}
                className={`cmd-item ${index === selectedIndex ? 'selected' : ''}`}
                role="option"
                aria-selected={index === selectedIndex}
                onClick={() => { cmd.action(); hideAfterAction(); }}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <span className="cmd-item-icon">{cmd.icon}</span>
                <span className="cmd-item-title">{cmd.title}</span>
                {cmd.subtitle && <span className="cmd-item-subtitle">{cmd.subtitle}</span>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

/** Global Cmd+K handler with Monaco conflict prevention, to be placed in App */
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

export default CommandPalette;
