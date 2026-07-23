/**
 * App — Root component with React Router v7
 * ===========================================
 * Provides the main layout shell with sidebar, terminal, command palette.
 */
// @ts-nocheck


import React, { Suspense, lazy, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useUiStore } from './stores/uiStore';
import { useChatStore } from './stores/chatStore';
import { checkHealth, fetchSystemMetrics } from './api/client';
import Sidebar from './components/Layout/Sidebar';
import ToastContainer from './components/UI/ToastContainer';
import PinModal from './components/UI/PinModal';
import FolderBrowser from './components/Editor/FolderBrowser';
import CommandPalette from './components/UI/CommandPalette';
import { useGlobalCommandPalette } from './components/UI/CommandPalette';
import KeyboardShortcutsModal from './components/UI/KeyboardShortcutsModal';
import MultiTerminalPanel from './components/UI/MultiTerminalPanel';
import OutputPanel from './components/UI/OutputPanel';
import { useTerminalStore } from './stores/terminalStore';
import { useThemeStore } from './stores/themeStore';
import { useEditorStore } from './stores/editorStore';
import { useLocalHistoryStore } from './stores/localHistoryStore';
import { isMonacoFocused } from './utils/domHelpers';
import { PluginLifecycleDispatcher } from './plugin/PluginManager';
import PluginPanelRoutes from './plugin/PluginManager';
import { usePluginRegistry } from './plugin/pluginRegistry';
import { examplePlugin } from './plugin/examplePlugin';

/* ─── Page loading fallback ────────────────────────────────── */
const PageLoadingFallback: React.FC = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: 10,
    color: 'var(--text-muted)',
    fontSize: 14,
  }}>
    <span style={{
      display: 'inline-block', width: 18, height: 18,
      border: '2px solid var(--glass-border)',
      borderTopColor: 'var(--accent-color)',
      borderRadius: '50%',
      animation: 'dex-spin 0.8s linear infinite',
    }} />
    Loading...
  </div>
);

// ─── Lazy-loaded page chunks ────────────────────────────────
const ChatPage = lazy(() => import('./components/Chat/ChatPage'));
const WikiPage = lazy(() => import('./pages/WikiPage'));
const AgentPage = lazy(() => import('./pages/AgentPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const SkillsPage = lazy(() => import('./pages/SkillsPage'));
const DataExtractionPage = lazy(() => import('./pages/DataExtractionPage'));
const GitPage = lazy(() => import('./pages/GitPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));
const PluginPage = lazy(() => import('./pages/PluginPage'));

type BottomPanelTab = 'terminal' | 'output';

const AppContent: React.FC = () => {
  const { systemStatus, setSystemStatus } = useUiStore();
  const { loadFromStorage } = useChatStore();
  const terminalVisible = useTerminalStore(s => s.visible);
  const toggleTerminal = useTerminalStore(s => s.toggleVisible);
  const addSession = useTerminalStore(s => s.addSession);
  const [shortcutsVisible, setShortcutsVisible] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomPanelTab>('terminal');

  // Register built-in plugins on mount
  useEffect(() => {
    usePluginRegistry.getState().register(examplePlugin);
  }, []);

  // Load theme preferences on mount
  useEffect(() => {
    try {
      useThemeStore.getState().load();
    } catch (e) {
      console.warn('[Theme] Failed to load preferences:', e);
    }
  }, []);

  // Auto-snapshot file changes to local history
  useEffect(() => {
    const unsub = useEditorStore.subscribe((state, prevState) => {
      if (!state.openFiles.length) return;
      const lh = useLocalHistoryStore.getState();
      if (!lh.autoSaveEnabled) return;

      for (const file of state.openFiles) {
        const prev = prevState.openFiles.find(f => f.path === file.path);
        // Snapshot NEW content when content changes (keeps current state in history)
        if (prev && prev.content !== file.content) {
          lh.addSnapshot({
            filePath: file.path,
            fileName: file.name,
            content: file.content,  // save current/new state
            source: file.isDirty ? 'auto' : 'manual',
            label: file.isDirty ? undefined : '수동 저장',
          });
        }
        // Snapshot on save transition: dirty → saved
        if (prev && prev.isDirty && !file.isDirty) {
          lh.addSnapshot({
            filePath: file.path,
            fileName: file.name,
            content: file.content,
            source: 'manual',
            label: '💾 저장 시점',
          });
        }
      }
    });
    return () => unsub();
  }, []);

  // Global Cmd+K handler (with Monaco conflict prevention)
  useGlobalCommandPalette();

  // Global `?` handler for Keyboard Shortcuts Guide (when NOT in Monaco)

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Cmd+Shift+F: Search in Files
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('agk:toggle-search'));
        return;
      }
      // Cmd+`: Toggle terminal
      if (e.key === '`' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        toggleTerminal();
        return;
      }
      // `?` or Cmd+/(Ctrl+/): Keyboard Shortcuts Guide
      if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.altKey && !isMonacoFocused()) {
        e.preventDefault();
        setShortcutsVisible(v => !v);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        setShortcutsVisible(v => !v);
        return;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggleTerminal]);

  useEffect(() => {
    loadFromStorage();

    const handlePinRequired = () => {
      useUiStore.getState().setPinModalVisible(true);
    };
    window.addEventListener('agk:pin-required', handlePinRequired);

    const pollSystemStatus = async () => {
      try {
        const health = await checkHealth();
        setSystemStatus({
          healthy: health.status === 'ok',
          backends: health.backends || {},
          ragFiles: parseInt(health.rag_index_files || '0'),
          covActive: health.cov_active || false,
        });
      } catch {
        setSystemStatus({ healthy: false });
      }

      try {
        const metrics = await fetchSystemMetrics();
        if (metrics.ok) {
          setSystemStatus({
            cpuPercent: metrics.cpu_percent || 0,
            memoryMb: metrics.memory_mb || 0,
            totalTokens: metrics.total_tokens || 0,
          });
        }
      } catch { /* silent */ }
    };

    pollSystemStatus();
    const interval = setInterval(pollSystemStatus, 10000);

    // Listen for global navigation events from CommandPalette / Wiki
    const handleNavigate = (e: CustomEvent) => {
      const path = e.detail;
      // Use window.location for simplicity across routes
      window.dispatchEvent(new CustomEvent('agk:pushstate', { detail: path }));
    };
    const handleChatSlash = (e: CustomEvent) => {
      // Navigate to chat and set input text
      const { text } = e.detail;
      window.dispatchEvent(new CustomEvent('agk:pushstate', { detail: '/chat' }));
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('agk:set-chat-input', { detail: { text } }));
      }, 300);
    };

    window.addEventListener('agk:navigate', handleNavigate as EventListener);
    window.addEventListener('agk:chat-slash', handleChatSlash as EventListener);

    return () => {
      window.removeEventListener('agk:pin-required', handlePinRequired);
      window.removeEventListener('agk:navigate', handleNavigate as EventListener);
      window.removeEventListener('agk:chat-slash', handleChatSlash as EventListener);
      clearInterval(interval);
    };
  }, []);

  // Simple pushstate-based routing for external events
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      const path = e.detail as string;
      if (path) window.location.hash = '#!' + path;
    };
    window.addEventListener('agk:pushstate', handler as EventListener);
    return () => window.removeEventListener('agk:pushstate', handler as EventListener);
  }, []);

  return (
    <div className="app-layout">
      <Sidebar toggleTerminal={toggleTerminal} />
      <div className="app-right-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <main className="main-content">
          <Suspense fallback={<PageLoadingFallback />}>
            <Routes>
              <Route path="/" element={<ChatPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/wiki" element={<WikiPage />} />
              <Route path="/agent" element={<AgentPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/data-extraction" element={<DataExtractionPage />} />
              <Route path="/git" element={<GitPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/plugins/*" element={<PluginPanelRoutes />} />
              <Route path="/plugins" element={<PluginPage />} />
            </Routes>
          </Suspense>
        </main>
        {/* Bottom Panel: Terminal + Output (toggleable) */}
        <div
          className="terminal-wrapper"
          style={{
            height: terminalVisible ? 220 : 0,
            minHeight: terminalVisible ? 180 : 0,
            transition: 'height 0.25s ease',
            overflow: 'hidden',
            borderTop: terminalVisible ? '1px solid var(--glass-border)' : 'none',
            background: '#0f1117',
          }}
        >
          {/* ── Bottom Panel Tab Bar ────────────────────────────── */}
          <div className="bottom-panel-tabs" style={{
            display: terminalVisible ? 'flex' : 'none',
          }}>
            <button
              className={`bottom-panel-tab ${bottomTab === 'terminal' ? 'active' : ''}`}
              onClick={() => setBottomTab('terminal')}
            >
              💻 Terminal
            </button>
            <button
              className={`bottom-panel-tab ${bottomTab === 'output' ? 'active' : ''}`}
              onClick={() => setBottomTab('output')}
            >
              📋 Output
            </button>
            <div className="bottom-panel-spacer" />
            <button
              className="bottom-panel-tab add-terminal-btn"
              onClick={() => addSession()}
              title="New terminal"
            >
              + New Term
            </button>
            <button
              className="bottom-panel-tab close-btn"
              onClick={toggleTerminal}
              title="Close"
            >
              ✕
            </button>
          </div>
          {terminalVisible && bottomTab === 'terminal' && <MultiTerminalPanel />}
          {terminalVisible && bottomTab === 'output' && <OutputPanel />}
        </div>
      </div>
      <PluginLifecycleDispatcher />
      <CommandPalette />
      <KeyboardShortcutsModal visible={shortcutsVisible} onClose={() => setShortcutsVisible(false)} />
      <ToastContainer />
      <PinModal />
      <FolderBrowser />
    </div>
  );
};

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
};

export default App;
