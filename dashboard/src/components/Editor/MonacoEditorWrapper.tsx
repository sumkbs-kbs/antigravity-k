/**
 * MonacoEditorWrapper — Dynamic import boundary for Monaco Editor
 * ================================================================
 * Wraps @monaco-editor/react in its own module so that Editor.tsx
 * can use React.lazy() to defer loading the ~500kB Monaco bundle
 * until the user opens a file.
 *
 * This file is the lazy-load entry point — it statically imports
 * Monaco Editor so Vite/Rollup can split it into its own chunk.
 *
 * Phase 19.2: Integrated Monaco's built-in TypeScript/JS language service
 * diagnostics marker listener and cursor position tracking for the
 * ProblemsPanel and StatusBar.
 */

import React, { useEffect, useRef } from 'react';
import Editor, { BeforeMount, OnMount } from '@monaco-editor/react';
import { useProblemsStore } from '../../stores/problemsStore';
import { useEditorStore } from '../../stores/editorStore';
import { useInlineEditStore } from '../../stores/inlineEditStore';
import { useThemeStore } from '../../stores/themeStore';

/* ─── Theme ─────────────────────────────────────────────────── */

const ANTIGRAVITY_THEME = {
  base: 'vs-dark' as const,
  inherit: true,
  rules: [
    { token: 'comment', foreground: '565f89' },
    { token: 'keyword', foreground: 'bb9af7' },
    { token: 'string', foreground: '9ece6a' },
    { token: 'number', foreground: 'ff9e64' },
    { token: 'type', foreground: '2ac3de' },
    { token: 'function', foreground: '7aa2f7' },
    { token: 'variable', foreground: 'c0caf5' },
    { token: 'constant', foreground: 'ff9e64' },
    { token: 'operator', foreground: '89ddff' },
  ],
  colors: {
    'editor.background': '#1a1b2e',
    'editor.foreground': '#c0caf5',
    'editor.lineHighlightBackground': '#292e42',
    'editor.selectionBackground': '#3b4261',
    'editorCursor.foreground': '#7c6aef',
    'editorLineNumber.foreground': '#3b4261',
    'editorLineNumber.activeForeground': '#565f89',
  },
};

/* ─── Props ─────────────────────────────────────────────────── */

interface Props {
  language: string;
  value: string;
  onChange: (value: string | undefined) => void;
  onMount: OnMount;
  editorRef: React.MutableRefObject<Parameters<OnMount>[0] | null>;
}

/* ─── Component ─────────────────────────────────────────────── */

const MonacoEditorWrapper: React.FC<Props> = ({ language, value, onChange, onMount, editorRef }) => {
  const { fontSize, showMinimap, showLineNumbers, wordWrap, tabSize } = useThemeStore();
  const markerListenerRef = useRef<{ dispose: () => void } | null>(null);
  const cursorListenerRef = useRef<{ dispose: () => void } | null>(null);
  const revealListenerRef = useRef<((e: Event) => void) | null>(null);

  const handleBeforeMount: BeforeMount = (monaco) => {
    monaco.editor.defineTheme('antigravity-dark', ANTIGRAVITY_THEME);

    // Enable TypeScript diagnostics — Monaco handles this automatically
    // for .ts/.tsx/.js/.jsx files via its built-in language service.
    // We also configure stricter TypeScript compiler options.
    try {
      // Configure TypeScript defaults for better diagnostics
      monaco.languages.typescript.typescriptDefaults.setDiagnosticsOptions({
        noSemanticValidation: false,
        noSyntaxValidation: false,
        diagnosticCodesToIgnore: [],
      });
      monaco.languages.typescript.javascriptDefaults.setDiagnosticsOptions({
        noSemanticValidation: false,
        noSyntaxValidation: false,
      });

      // Add common type definitions for better intellisense
      monaco.languages.typescript.typescriptDefaults.setCompilerOptions({
        target: monaco.languages.typescript.ScriptTarget.ES2022,
        allowNonTsExtensions: true,
        moduleResolution: monaco.languages.typescript.ModuleResolutionKind.NodeJs,
        module: monaco.languages.typescript.ModuleKind.ESNext,
        noEmit: true,
        strict: true,
        esModuleInterop: true,
        jsx: monaco.languages.typescript.JsxEmit.React,
        allowJs: true,
        checkJs: false,
      });
    } catch { /* ignore — TS config is best-effort */ }
  };

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    onMount(editor, monaco);

    // Store editor instance for overlay widgets
    useEditorStore.getState().setMonacoEditor(editor);

    // ─── Marker Listener: Capture diagnostics from Monaco ─────────
    // Monaco's built-in TypeScript/JavaScript language service
    // produces markers automatically. We listen for changes and
    // sync them to our ProblemsStore.
    const { activeFilePath, openFiles } = useEditorStore.getState();
    const currentFile = openFiles.find(f => f.path === activeFilePath);
    const model = editor.getModel();
    const modelUri = model?.uri;

    const updateMarkers = () => {
      if (!activeFilePath || !currentFile || !modelUri) return;

      const markers = monaco.editor.getModelMarkers({ resource: modelUri });
      if (markers.length > 0 || useProblemsStore.getState().problems.length > 0) {
        useProblemsStore.getState().setProblems(
          activeFilePath,
          currentFile.name,
          markers,
        );
      }
    };

    // Debounced marker update on content change
    let markerTimeout: ReturnType<typeof setTimeout> | null = null;
    const debouncedUpdate = () => {
      if (markerTimeout) clearTimeout(markerTimeout);
      markerTimeout = setTimeout(updateMarkers, 300);
    };

    // Listen for marker changes via Monaco's onDidChangeMarkers
    const markerListener = monaco.editor.onDidChangeMarkers((resources: any[]) => {
      if (resources.some((r: any) => r.toString() === modelUri?.toString())) {
        debouncedUpdate();
      }
    });
    markerListenerRef.current = markerListener;

    // Also update on content change
    const contentChangeDisposable = editor.onDidChangeModelContent(() => {
      debouncedUpdate();
    });

    // ─── Cursor Position Listener ──────────────────────────────────
    cursorListenerRef.current = editor.onDidChangeCursorPosition((e) => {
      window.dispatchEvent(new CustomEvent('agk:cursor-position', {
        detail: { line: e.position.lineNumber, column: e.position.column },
      }));
    });

    // ─── Reveal Line Listener (from ProblemsPanel click) ──────────
    const handleRevealLine = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.line) {
        editor.revealLineInCenter(detail.line);
        editor.setPosition({ lineNumber: detail.line, column: detail.column || 1 });
        editor.focus();
      }
    };
    window.addEventListener('agk:editor-reveal-line', handleRevealLine);
    revealListenerRef.current = handleRevealLine;

    // ─── Ctrl+K: Inline Edit (Cursor-style) ───────────────────────
    const inlineEditAction = editor.addAction({
      id: 'inline-edit',
      label: 'Inline Edit (Ctrl+K)',
      keybindings: [
        monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK,
      ],
      contextMenuGroupId: '1_modification',
      contextMenuOrder: 1,
      run: (ed) => {
        const position = ed.getPosition();
        if (!position) return;

        const { activeFilePath } = useEditorStore.getState();
        if (activeFilePath) {
          useInlineEditStore.getState().openEditor(
            activeFilePath,
            position.lineNumber,
            position.column,
          );
        }
      },
    });

    // ─── Listen for Ctrl+Enter to accept inline edit suggestion ────
    const inlineAcceptAction = editor.addAction({
      id: 'inline-accept',
      label: 'Accept Inline Edit Suggestion',
      keybindings: [
        monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
      ],
      run: () => {
        const { phase } = useInlineEditStore.getState();
        if (phase === 'preview') {
          // Dispatch custom event to trigger accept
          window.dispatchEvent(new CustomEvent('agk:inline-accept'));
        } else if (phase === 'input') {
          // Dispatch custom event to trigger suggest
          window.dispatchEvent(new CustomEvent('agk:inline-suggest'));
        }
      },
    });

    // ─── Initial marker sync after a brief delay ──────────────────
    setTimeout(updateMarkers, 500);

    // Clean up on unmount (for file switch)
    return () => {
      contentChangeDisposable?.dispose();
    };
  };

  // Clean up global listeners on unmount
  useEffect(() => {
    return () => {
      if (markerListenerRef.current) {
        markerListenerRef.current.dispose();
        markerListenerRef.current = null;
      }
      if (cursorListenerRef.current) {
        cursorListenerRef.current.dispose();
        cursorListenerRef.current = null;
      }
      if (revealListenerRef.current) {
        window.removeEventListener('agk:editor-reveal-line', revealListenerRef.current);
        revealListenerRef.current = null;
      }
      // Clear editor instance from store
      useEditorStore.getState().setMonacoEditor(null);
    };
  }, []);

  return (
    <Editor
      defaultLanguage={language}
      language={language}
      defaultValue={value}
      value={value}
      theme="antigravity-dark"
      beforeMount={handleBeforeMount}
      onMount={handleMount}
      onChange={onChange}
      options={{
        fontSize,
        fontFamily: "'JetBrains Mono', monospace",
        lineNumbers: showLineNumbers ? 'on' : 'off',
        minimap: { enabled: showMinimap, scale: 1, showSlider: 'always' },
        scrollBeyondLastLine: false,
        wordWrap,
        tabSize,
        renderWhitespace: 'selection',
        padding: { top: 12 },
        automaticLayout: true,
        bracketPairColorization: { enabled: true },
        smoothScrolling: true,
        cursorBlinking: 'smooth',
        cursorSmoothCaretAnimation: 'on',
        suggest: {
          showKeywords: true,
          showSnippets: true,
        },
        // Diagnostics display
        overviewRulerLanes: 3,
        overviewRulerBorder: true,
        hideCursorInOverviewRuler: false,
        // Sticky scroll (VS Code-like)
        stickyScroll: { enabled: true },
      }}
      loading={
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: '100%', color: '#666', fontSize: 14,
        }}>
          Loading editor...
        </div>
      }
    />
  );
};

export default MonacoEditorWrapper;
