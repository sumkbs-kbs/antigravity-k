/**
 * InlineEditOverlay — Cursor-style inline code editing overlay
 * ==============================================================
 * Uses Monaco Editor's IContentWidget API to position the overlay
 * precisely at the cursor line/column, scrolling naturally with
 * the editor content. Parses unified diff format (--- a/+++ b/)
 * from AI suggestions for proper +/-/context line display.
 *
 * Phases:
 *   idle → input → loading → preview → applied
 *
 * Inspired by Cursor IDE's inline edit feature.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useInlineEditStore } from '../../stores/inlineEditStore';
import { useChangeStore } from '../../stores/changeStore';
import { useEditorStore } from '../../stores/editorStore';
import { useUiStore } from '../../stores/uiStore';
import { parseDiff, isUnifiedDiff, applyUnifiedDiff, type DiffLine } from '../../utils/diffParser';

/* ─── Monaco IContentWidget wrapper ────────────────────────── */

/**
 * Creates a Monaco IContentWidget positioned at the given line/column.
 * The widget's DOM node is a container div; callers render into it
 * via React portal.
 */
function createInlineWidget(
  editor: any,
  lineNumber: number,
  column: number,
): { widget: any; container: HTMLDivElement } {
  const container = document.createElement('div');
  container.className = 'inline-edit-widget-container';

  const widget: any = {
    getId: () => 'agk-inline-edit-widget',
    getDomNode: () => container,
    getPosition: () => ({
      position: { lineNumber, column },
      preference: [
        // ContentWidgetPositionPreference values (stable Monaco API):
        // 0 = ABOVE, 1 = BELOW, 2 = EXACT
        0, 1, // Try ABOVE first, fall back to BELOW
      ],
    }),
  };

  editor.addContentWidget(widget);
  return { widget, container };
}

function removeInlineWidget(editor: any, widget: any) {
  try {
    editor.removeContentWidget(widget);
  } catch {
    // Widget may already be removed
  }
}

/* ─── InlineEditOverlay ────────────────────────────────────── */

const InlineEditOverlay: React.FC = () => {
  const {
    phase, cursorLine, cursorColumn,
    instruction, suggestedCode, error,
    closeEditor, setInstruction,
  } = useInlineEditStore();

  const { activeFilePath, updateFileContent } = useEditorStore();
  const { addToast } = useUiStore();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const portalTargetRef = useRef<HTMLDivElement | null>(null);
  const [portalContainer, setPortalContainer] = useState<HTMLDivElement | null>(null);

  // ── Parse suggested code as unified diff if applicable ────
  const parsedDiffLines: DiffLine[] = React.useMemo(() => {
    if (!suggestedCode) return [];
    if (isUnifiedDiff(suggestedCode)) {
      return parseDiff(suggestedCode);
    }
    // Plain code: treat all as added lines
    return suggestedCode.split('\n').map(line => ({
      type: 'added' as const,
      content: line || ' ',
    }));
  }, [suggestedCode]);

  const isDiffFormat = React.useMemo(
    () => isUnifiedDiff(suggestedCode),
    [suggestedCode],
  );

  // ── Manage Monaco IContentWidget lifecycle ─────────────────
  useEffect(() => {
    const editor = useEditorStore.getState().monacoEditor;
    if (!editor || phase === 'idle') {
      setPortalContainer(null);
      return;
    }

    const { widget, container } = createInlineWidget(
      editor,
      cursorLine || 1,
      cursorColumn || 1,
    );
    portalTargetRef.current = container;
    setPortalContainer(container);

    return () => {
      removeInlineWidget(editor, widget);
      portalTargetRef.current = null;
      setPortalContainer(null);
    };
  }, [phase, cursorLine, cursorColumn]);

  // ── Re-layout widget when phase changes (size changes) ────
  useEffect(() => {
    if (phase !== 'idle') {
      const editor = useEditorStore.getState().monacoEditor;
      if (editor) {
        // Force Monaco to re-layout the widget after DOM updates
        requestAnimationFrame(() => {
          try { editor.layoutContentWidget?.({ getId: () => 'agk-inline-edit-widget' } as any); } catch {}
        });
      }
    }
  }, [phase, parsedDiffLines]);

  // ── Get suggestion from backend ─────────────────────────────
  const fetchSuggestion = useCallback(async (instructionText: string) => {
    if (!activeFilePath || !instructionText.trim()) return;

    const { openFiles } = useEditorStore.getState();
    const currentFile = openFiles.find(f => f.path === activeFilePath);
    if (!currentFile) return;

    const store = useInlineEditStore.getState();
    store.setInstruction(instructionText);
    store.setLoading(true);

    try {
      const res = await fetch('/api/code/inline-suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_path: activeFilePath,
          language: currentFile.language,
          original_code: currentFile.content,
          instruction: instructionText,
          cursor_line: cursorLine,
          cursor_column: cursorColumn,
        }),
      });
      const data = await res.json();
      if (data.ok && data.suggested_code) {
        store.setSuggestedCode(data.suggested_code, data.start_line || cursorLine, data.end_line || cursorLine);
      } else {
        store.setError(data.error || 'Failed to generate suggestion');
        addToast('❌ 제안 생성 실패', 'error');
      }
    } catch (err: any) {
      store.setError(err.message);
      addToast(`❌ 오류: ${err.message}`, 'error');
    }
  }, [activeFilePath, cursorLine, cursorColumn, addToast]);

  // ── Apply suggestion ───────────────────────────────────────
  const handleApply = useCallback(() => {
    if (!suggestedCode || !activeFilePath) return;

    const store = useInlineEditStore.getState();
    const { openFiles } = useEditorStore.getState();
    const currentFile = openFiles.find(f => f.path === activeFilePath);
    if (!currentFile) return;

    const originalContent = currentFile.content;
    const fileName = currentFile.name;

    let newContent: string;
    let description: string;

    if (isDiffFormat) {
      // Unified diff: apply diff to original content
      newContent = applyUnifiedDiff(originalContent, suggestedCode);
      description = `인라인 편집 (diff): ${instruction || fileName}`;
    } else {
      // Plain code: replace the target line range
      const lines = originalContent.split('\n');
      const startIdx = store.startLine - 1;
      const endIdx = store.endLine - 1;
      const suggestionLines = suggestedCode.split('\n');
      lines.splice(startIdx, endIdx - startIdx + 1, ...suggestionLines);
      newContent = lines.join('\n');
      description = `인라인 편집: ${instruction || fileName}`;
    }

    updateFileContent(activeFilePath, newContent);

    useChangeStore.getState().addChange({
      filePath: activeFilePath,
      fileName,
      originalContent,
      newContent,
      description,
    });

    store.applySuggestion();
    addToast('✅ 인라인 제안이 적용되었습니다', 'success');
    setTimeout(() => store.closeEditor(), 800);
  }, [suggestedCode, activeFilePath, instruction, updateFileContent, addToast, isDiffFormat]);

  // ── Reject suggestion ──────────────────────────────────────
  const handleReject = useCallback(() => {
    useInlineEditStore.getState().rejectSuggestion();
    addToast('❌ 제안 거절됨', 'info');
  }, [addToast]);

  // ── Send instruction (Enter) ───────────────────────────────
  const handleSendInstruction = useCallback(() => {
    if (instruction.trim()) {
      fetchSuggestion(instruction);
    }
  }, [instruction, fetchSuggestion]);

  // ── Refs for stable event handler references ─────────────────
  const handleAcceptRef = useRef<() => void>(() => {});
  const handleSuggestRef = useRef<(text: string) => void>(() => {});

  useEffect(() => { handleAcceptRef.current = handleApply; }, [handleApply]);
  useEffect(() => { handleSuggestRef.current = fetchSuggestion; }, [fetchSuggestion]);

  // ── Listen for Monaco Ctrl+Enter shortcuts (setup once) ─────
  useEffect(() => {
    const onAccept = () => {
      const s = useInlineEditStore.getState();
      if (s.phase === 'preview') handleAcceptRef.current();
    };
    const onSuggest = () => {
      const s = useInlineEditStore.getState();
      if (s.phase === 'input' && s.instruction.trim()) {
        handleSuggestRef.current(s.instruction);
      }
    };
    window.addEventListener('agk:inline-accept', onAccept);
    window.addEventListener('agk:inline-suggest', onSuggest);
    return () => {
      window.removeEventListener('agk:inline-accept', onAccept);
      window.removeEventListener('agk:inline-suggest', onSuggest);
    };
  }, []);

  // ── Auto-focus input when entering input phase ──────────────
  useEffect(() => {
    if (phase === 'input' && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [phase]);

  // ── Keyboard handlers ────────────────────────────────────────
  const handleInputKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.shiftKey) return;
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSendInstruction();
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSendInstruction();
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      closeEditor();
    }
  }, [handleSendInstruction, closeEditor]);

  const handlePreviewKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Tab' || (e.key === 'Enter' && (e.metaKey || e.ctrlKey))) {
      e.preventDefault();
      handleApply();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleReject();
    }
  }, [handleApply, handleReject]);

  // ── Don't render if idle ────────────────────────────────────
  if (phase === 'idle') return null;

  const overlayContent = (
    <div
      className="inline-edit-overlay glass-panel"
      style={{
        width: 380,
        maxWidth: 'calc(100vw - 32px)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      }}
    >
      {phase === 'input' && (
        <div className="inline-edit-input-phase">
          <div className="inline-edit-header">
            <span className="inline-edit-title">✏️ Edit</span>
            <span className="inline-edit-shortcuts">
              <kbd>Enter</kbd> suggest · <kbd>Shift+Enter</kbd> newline · <kbd>Esc</kbd> cancel
            </span>
          </div>
          <textarea
            ref={inputRef}
            className="inline-edit-textarea"
            value={instruction}
            onChange={e => setInstruction(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Describe what to change... (e.g., 'rename to camelCase', 'add error handling')"
            rows={3}
            autoFocus
          />
          <div className="inline-edit-actions">
            <button className="glass-btn small" onClick={closeEditor}>Cancel</button>
            <button
              className="glow-btn"
              onClick={handleSendInstruction}
              disabled={!instruction.trim()}
              style={{ fontSize: 11, padding: '4px 12px' }}
            >
              ✨ Suggest
            </button>
          </div>
        </div>
      )}

      {phase === 'loading' && (
        <div className="inline-edit-loading">
          <span className="spinner spinner-sm" />
          <span>Generating suggestion...</span>
        </div>
      )}

      {phase === 'preview' && (
        <div className="inline-edit-preview" onKeyDown={handlePreviewKeyDown} tabIndex={0}>
          <div className="inline-edit-preview-header">
            <span className="inline-edit-title">💡 Suggestion</span>
            <span className="inline-edit-shortcuts">
              <kbd>Tab</kbd> accept · <kbd>Esc</kbd> reject
            </span>
          </div>
          {isDiffFormat ? (
            /* ── Unified Diff Preview ─────────────────────────── */
            <div className="inline-edit-diff unified-diff">
              {parsedDiffLines.map((line, i) => {
                let className = 'inline-edit-diff-line';
                let gutter = ' ';
                if (line.type === 'added') {
                  className += ' diff-added';
                  gutter = '+';
                } else if (line.type === 'removed') {
                  className += ' diff-removed';
                  gutter = '-';
                } else if (line.type === 'hunk') {
                  className += ' diff-hunk';
                  gutter = '@';
                } else if (line.type === 'context') {
                  className += ' diff-context';
                  gutter = ' ';
                } else {
                  className += ' diff-header';
                  gutter = ' ';
                }
                return (
                  <div key={i} className={className}>
                    <span className="inline-edit-diff-gutter">{gutter}</span>
                    <span className="inline-edit-diff-text">{line.content || ' '}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            /* ── Plain Code Preview ────────────────────────────── */
            <div className="inline-edit-diff">
              {parsedDiffLines.map((line, i) => (
                <div key={i} className="inline-edit-diff-line added">
                  <span className="inline-edit-diff-gutter">+</span>
                  <span className="inline-edit-diff-text">{line.content || ' '}</span>
                </div>
              ))}
            </div>
          )}
          <div className="inline-edit-actions">
            <button className="glass-btn small" onClick={handleReject}>✕ Reject</button>
            <button className="glow-btn" onClick={handleApply} style={{ fontSize: 11, padding: '4px 12px' }}>
              ✓ Accept (Tab)
            </button>
          </div>
        </div>
      )}

      {phase === 'applied' && (
        <div className="inline-edit-applied">
          <span>✅ Applied</span>
        </div>
      )}

      {error && (
        <div className="inline-edit-error">⚠️ {error}</div>
      )}
    </div>
  );

  // Render into Monaco's IContentWidget container via portal
  if (portalContainer) {
    return createPortal(overlayContent, portalContainer);
  }

  // Fallback: render in-place (before widget is created)
  return (
    <div style={{
      position: 'fixed',
      zIndex: 100,
      top: Math.max(8, Math.min((cursorLine || 1) * 20 - 40, 200)),
      right: 16,
    }}>
      {overlayContent}
    </div>
  );
};

export default InlineEditOverlay;
