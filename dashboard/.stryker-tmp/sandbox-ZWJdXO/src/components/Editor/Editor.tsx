/**
 * Editor — Monaco Editor wrapper component
 * ==========================================
 * Uses @monaco-editor/react with custom dark theme.
 * Handles file opening, language detection, tab management.
 *
 * Phase 19.2: Integrated ProblemsPanel (bottom pane) and StatusBar
 * for VS Code-style diagnostics display.
 */
// @ts-nocheck


import React, { Suspense, lazy, useCallback, useRef, useEffect, useState, useMemo } from 'react';
import type { OnMount } from '@monaco-editor/react';
import { useEditorStore } from '../../stores/editorStore';
import { useProblemsStore } from '../../stores/problemsStore';
import { useUiStore } from '../../stores/uiStore';
import { useInlineEditStore } from '../../stores/inlineEditStore';
import ProblemsPanel from './ProblemsPanel';
import StatusBar from './StatusBar';
import InlineEditOverlay from './InlineEditOverlay';

// Lazy-load Monaco Editor (~500kB, split into separate chunk)
const MonacoEditorWrapper = lazy(() => import('./MonacoEditorWrapper'));

/* ─── Editor Loading Fallback ──────────────────────────────── */
const EditorFallback: React.FC = () => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: '100%', color: '#666', fontSize: 14,
  }}>
    <span style={{
      display: 'inline-block', width: 16, height: 16, marginRight: 8,
      border: '2px solid #333', borderTopColor: '#007acc',
      borderRadius: '50%', animation: 'dex-spin 0.8s linear infinite',
    }} />
    Loading editor...
  </div>
);

/* ─── Memoized Editor Tab Bar ──────────────────────────────── */
interface EditorTabsProps {
  openFiles: Array<{ path: string; name: string; isDirty: boolean; language: string }>;
  activeFilePath: string | null;
  saving: boolean;
  onSetActiveFile: (path: string) => void;
  onCloseFile: (path: string) => void;
  onSave: () => void;
}

const EditorTabs: React.FC<EditorTabsProps> = React.memo(({
  openFiles, activeFilePath, saving,
  onSetActiveFile, onCloseFile, onSave,
}) => {
  if (openFiles.length === 0) {
    return (
      <div className="editor-tabs" style={{
        display: 'flex',
        background: '#252526',
        borderBottom: '1px solid #1e1e1e',
        overflowX: 'auto',
        flexShrink: 0,
      }}>
        <div className="editor-tab active" style={{
          padding: '10px 16px',
          background: '#1e1e1e',
          color: '#ccc',
          fontSize: 13,
          display: 'flex',
          alignItems: 'center',
          borderTop: '1px solid #007acc',
          cursor: 'pointer',
        }}>
          <svg style={{ width: 14, height: 14, marginRight: 6 }} viewBox="0 0 16 16" fill="#519aba">
            <path d="M13.71 4.29l-3-3L10 1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1V5l-.29-.71zM10 2.41L12.59 5H10V2.41zM13 14H4V2h5v4h4v8z" />
          </svg>
          <span id="editor-title">Welcome</span>
        </div>
      </div>
    );
  }

  return (
    <div className="editor-tabs" style={{
      display: 'flex',
      background: '#252526',
      borderBottom: '1px solid #1e1e1e',
      overflowX: 'auto',
      flexShrink: 0,
    }}>
      {openFiles.map(file => {
        const isActive = file.path === activeFilePath;
        return (
          <div
            key={file.path}
            className={`editor-tab ${isActive ? 'active' : ''}`}
            style={{
              padding: '8px 12px',
              background: isActive ? '#1e1e1e' : '#2d2d2d',
              color: isActive ? '#fff' : '#999',
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              borderTop: isActive ? '1px solid #007acc' : '1px solid transparent',
              cursor: 'pointer',
              fontFamily: 'sans-serif',
              whiteSpace: 'nowrap',
            }}
            onClick={() => onSetActiveFile(file.path)}
          >
            <span>{file.name}</span>
            {file.isDirty && <span style={{ color: '#ff9e64', fontSize: 10 }}>●</span>}
            {file.isDirty && isActive && (
              <button
                className="tab-save-btn"
                onClick={e => {
                  e.stopPropagation();
                  onSave();
                }}
                title="Save (Ctrl+S)"
                style={{
                  background: 'none',
                  border: 'none',
                  color: saving ? '#888' : '#10b981',
                  cursor: saving ? 'wait' : 'pointer',
                  fontSize: 12,
                  padding: '0 2px',
                  lineHeight: 1,
                }}
                disabled={saving}
              >
                💾
              </button>
            )}
            <button
              className="tab-close-btn"
              onClick={e => {
                e.stopPropagation();
                onCloseFile(file.path);
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#666',
                cursor: 'pointer',
                fontSize: 14,
                padding: '0 2px',
                lineHeight: 1,
              }}
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
});

EditorTabs.displayName = 'EditorTabs';

const CodeEditor: React.FC = () => {
  const openFiles = useEditorStore(s => s.openFiles);
  const activeFilePath = useEditorStore(s => s.activeFilePath);
  const closeFile = useEditorStore(s => s.closeFile);
  const setActiveFile = useEditorStore(s => s.setActiveFile);
  const updateFileContent = useEditorStore(s => s.updateFileContent);
  const saveFile = useEditorStore(s => s.saveFile);
  const { setActiveFile: setProblemsActiveFile } = useProblemsStore();
  const { addToast } = useUiStore();
  const activeFile = openFiles.find(f => f.path === activeFilePath);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const [saving, setSaving] = useState(false);

  // Sync active file with problems store
  useEffect(() => {
    setProblemsActiveFile(activeFilePath);
  }, [activeFilePath, setProblemsActiveFile]);

  // Update problems when active file changes (re-scan markers)
  useEffect(() => {
    if (activeFilePath && editorRef.current) {
      // The MonacoEditorWrapper handles marker syncing via onDidChangeMarkers
      // But we also trigger an update when the active file changes
      const editor = editorRef.current;
      const model = editor.getModel();
      if (model) {
        try {
          // Force a marker update by dispatching a delayed call
          setTimeout(() => {
            const markers = (window as any).monaco?.editor.getModelMarkers({ resource: model.uri }) || [];
            if (markers.length > 0) {
              const file = useEditorStore.getState().openFiles.find(f => f.path === activeFilePath);
              if (file) {
                useProblemsStore.getState().setProblems(activeFilePath, file.name, markers);
              }
            }
          }, 100);
        } catch { /* ignore */ }
      }
    }
  }, [activeFilePath]);

  const handleSave = useCallback(async () => {
    const state = useEditorStore.getState();
    const { activeFilePath: currentPath, openFiles: currentFiles, saveFile: doSave } = state;
    if (!currentPath) return;
    const file = currentFiles.find(f => f.path === currentPath);
    if (!file || !file.isDirty) return;

    setSaving(true);
    const ok = await doSave(currentPath);
    setSaving(false);

    if (ok) {
      addToast(`✅ ${file.name} 저장됨`, 'success');
    } else {
      addToast(`❌ ${file.name} 저장 실패`, 'error');
    }
  }, [addToast]);

  const handleEditorDidMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;

    // Register Ctrl+S / Cmd+S keybinding within Monaco
    editor.addAction({
      id: 'save-file',
      label: 'Save File',
      keybindings: [
        monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
      ],
      run: () => {
        window.dispatchEvent(new CustomEvent('agk:editor-save'));
      },
    });

    // Dispatch layout on mount
    setTimeout(() => editor.layout(), 100);
    // ResizeObserver to auto-layout
    const container = editor.getContainerDomNode();
    if (container) {
      const observer = new ResizeObserver(() => {
        try { editor.layout(); } catch {}
      });
      observer.observe(container);
    }
  }, []);

  const handleChange = useCallback((value: string | undefined) => {
    if (activeFilePath && value !== undefined) {
      updateFileContent(activeFilePath, value);
    }
  }, [activeFilePath, updateFileContent]);

  // Listen for save events (from Monaco keybinding or Ctrl+S globally)
  useEffect(() => {
    const handler = () => handleSave();
    window.addEventListener('agk:editor-save', handler);
    return () => window.removeEventListener('agk:editor-save', handler);
  }, [handleSave]);

  /** Check if a Monaco Editor element is focused */
  function isMonacoFocused(): boolean {
    const active = document.activeElement;
    if (!active) return false;
    return !!active.closest?.('.monaco-editor') ||
           !!active.closest?.('.monaco-inputbox') ||
           active.className?.includes?.('monaco');
  }

  // Global Ctrl+S / Cmd+S handler (skip when Monaco is focused)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
        if (isMonacoFocused()) return;
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSave]);

  return (
    <div className="ide-editor" style={{
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      background: '#1e1e1e',
      flex: 1,
      minHeight: 0,
    }}>
      {/* Editor Panel (tabs + content) */}
      <div className="ide-editor-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
        {/* Editor Tabs (memoized) */}
        <EditorTabs
          openFiles={openFiles}
          activeFilePath={activeFilePath}
          saving={saving}
          onSetActiveFile={setActiveFile}
          onCloseFile={closeFile}
          onSave={handleSave}
        />

        {/* Editor Content */}
        <div className="editor-content" style={{ flex: 1, position: 'relative', padding: 0, minHeight: 0 }}>
          {activeFile ? (
            <Suspense fallback={<EditorFallback />}>
              <MonacoEditorWrapper
                key={activeFile.path}
                language={activeFile.language}
                value={activeFile.content}
                onChange={handleChange}
                onMount={handleEditorDidMount}
                editorRef={editorRef}
              />
            </Suspense>
          ) : (
            <div
              id="editor-placeholder"
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                color: '#666',
                fontSize: 14,
                pointerEvents: 'none',
                textAlign: 'center',
              }}
            >
              Select a file from the explorer to view its contents.
            </div>
          )}

          {/* Inline Edit Overlay (Ctrl+K) */}
          <InlineEditOverlay />
        </div>
      </div>

      {/* Problems Panel (bottom pane, collapsible) */}
      <ProblemsPanel />

      {/* Status Bar (bottom) */}
      <StatusBar />
    </div>
  );
};

export default CodeEditor;
