/**
 * ChatPage — Agent Workspace (Antigravity × Codex × Unsloth)
 * ==========================================================
 * Composition mirrors the three reference screenshots:
 * - Antigravity: right-hand 환경 rail (변경 사항 / 로그 / branch /
 *   커밋·푸시 / 풀 리퀘스트 / 파일 액티브티 / 소스-MCP)
 * - Codex: activity feed (user prompt bubble, working indicator,
 *   file-edit cards, queued messages), breadcrumb top bar, Open IDE
 * - Unsloth: empty-state hero (mascot + "Ready when you are") with a
 *   large centered composer and chip toolbar (+, 전체 액세스, Search,
 *   Code, MCP, mic, round send)
 *
 * When a message is sent while the agent is streaming, the text is
 * queued and flushed automatically when the run finishes (Codex-style).
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { useUiStore } from '../../stores/uiStore';
import { useEditorStore } from '../../stores/editorStore';
import { useChangeStore } from '../../stores/changeStore';
import { streamChatCompletion, fetchModels, type ModelInfo } from '../../api/client';
import { useEventWebSocket } from '../../hooks/useEventWebSocket';
import { detectChangesFromAssistantContent, registerFileModification } from '../../utils/changeDetector';
import { firePluginHook } from '../../plugin/pluginRegistry';
import ChatMessage from './ChatMessage';
import ChatHistory from './ChatHistory';
import CodeEditor from '../Editor/Editor';
import ArtifactPreview from '../Editor/ArtifactPreview';
import ChangePanel from '../Editor/ChangePanel';
import EnvironmentPanel, { type EnvPanelTab } from './EnvironmentPanel';
import {
  WorkingIndicator,
  StreamErrorBanner,
  FileEditCard,
  QueuedMessagesCard,
} from './ChatActivity';

const MODEL_LABELS: Record<string, string> = {
  default: '5.6 Sol High',
  'codex-5.6-sol-high': '5.6 Sol High',
  'qwen-3.8-27b-gguf': 'Qwen 3.8 27B',
  'gemma-4-27b': 'Gemma 4 27B',
  'llama-3.2-mlx': 'Llama 3.2 3B',
};

export const ChatPage: React.FC = () => {
  const {
    messages, isStreaming, selectedModel, isPlanMode, isTddMode,
    activeSession,
    addMessage, updateLastAssistantMessage, saveToStorage,
    setStreaming, appendToCurrentAssistantContent,
    loadFromStorage, setSelectedModel,
  } = useChatStore();

  const { addToast } = useUiStore();
  const { previewVisible, openFile } = useEditorStore();
  const { setPanelVisible: setChangePanelVisible } = useChangeStore();
  const pendingChangeCount = useChangeStore((s) => s.changes.filter((c) => c.status === 'pending').length);

  /* ─── States ─────────────────────────────────────────────── */
  const [inputText, setInputText] = useState<string>('');
  const [queuedMessages, setQueuedMessages] = useState<string[]>([]);
  const [queueCollapsed, setQueueCollapsed] = useState<boolean>(false);

  const [actionMenuOpen, setActionMenuOpen] = useState<boolean>(false);
  const [modelDropdownOpen, setModelDropdownOpen] = useState<boolean>(false);
  const [accessDropdownOpen, setAccessDropdownOpen] = useState<boolean>(false);
  const [mcpMenuOpen, setMcpMenuOpen] = useState<boolean>(false);
  const [mcpEnabled, setMcpEnabled] = useState<boolean>(true);
  const [webSearch, setWebSearch] = useState<boolean>(false);
  const [codeMode, setCodeMode] = useState<boolean>(false);
  const [accessMode, setAccessMode] = useState<'full_access' | 'restricted'>('full_access');

  const [envPanelOpen, setEnvPanelOpen] = useState<boolean>(true);
  const [envTab, setEnvTab] = useState<EnvPanelTab>('env');
  const [historyVisible, setHistoryVisible] = useState<boolean>(false);

  const [streamError, setStreamError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number>(0);

  const [workspaceContext, setWorkspaceContext] = useState({
    project_name: 'Ssak-Ai',
    target: '로컬',
    branch: 'codex/m1-task-events',
  });

  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);

  /* ─── Refs ───────────────────────────────────────────────── */
  const abortRef = useRef<AbortController | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queueRef = useRef<string[]>([]);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selectedModelRef = useRef(selectedModel);
  const isPlanModeRef = useRef(isPlanMode);
  const isTddModeRef = useRef(isTddMode);
  const runRef = useRef<(text: string) => Promise<void>>(async () => {});

  useEffect(() => {
    selectedModelRef.current = selectedModel;
    isPlanModeRef.current = isPlanMode;
    isTddModeRef.current = isTddMode;
  }, [isPlanMode, isTddMode, selectedModel]);

  /* ─── Init ───────────────────────────────────────────────── */
  useEffect(() => {
    loadFromStorage();
    fetchModels()
      .then(models => setAvailableModels(models))
      .catch(() => {});
  }, [loadFromStorage]);

  useEffect(() => {
    fetch('/api/workspace/context')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setWorkspaceContext({
            project_name: data.project_name || 'Ssak-Ai',
            target: data.target || '로컬',
            branch: data.branch || 'codex/m1-task-events',
          });
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  const handleToggleAccessMode = async (mode: 'full_access' | 'restricted') => {
    try {
      await fetch('/api/system/access-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      setAccessMode(mode);
      setAccessDropdownOpen(false);
      addToast(mode === 'full_access' ? '전체 액세스 모드 허용' : '읽기 전용 샌드박스로 전환', 'info');
    } catch {
      setAccessMode(mode);
      setAccessDropdownOpen(false);
    }
  };

  /* ─── WebSocket event listeners ──────────────────────────── */
  useEventWebSocket({
    onFileOpened: (data) => {
      const filePath = data?.filepath;
      if (filePath) {
        const fileName = filePath.split(/[/\\]/).pop() || 'unknown';
        fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`)
          .then(r => r.ok ? r.json() : null)
          .then(d => {
            if (d?.content !== undefined) {
              openFile(filePath, fileName, d.content);
              setEnvPanelOpen(true);
              setEnvTab('code');
            }
          })
          .catch(() => {});
      }
    },
    onFileModified: (data) => {
      const filePath = data?.filepath;
      if (filePath) {
        const fileName = filePath.split(/[/\\]/).pop() || 'unknown';
        fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`)
          .then(r => r.ok ? r.json() : null)
          .then(d => {
            if (d?.content !== undefined) {
              openFile(filePath, fileName, d.content);
            }
          })
          .catch(() => {});
        registerFileModification(filePath, fileName)
          .then((registered) => {
            if (registered) addToast(`📋 변경 감지: ${fileName}`, 'info');
          })
          .catch(() => {});
      }
    },
  });

  /* ─── Elapsed timer while streaming ──────────────────────── */
  const startElapsedTimer = useCallback(() => {
    setElapsed(0);
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    elapsedTimerRef.current = setInterval(() => {
      setElapsed((v) => v + 1);
    }, 1000);
  }, []);

  const stopElapsedTimer = useCallback(() => {
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current);
      elapsedTimerRef.current = null;
    }
  }, []);

  useEffect(() => () => stopElapsedTimer(), [stopElapsedTimer]);

  /* ─── Send / queue / run loop ────────────────────────────── */
  const runCompletion = useCallback(async (text: string) => {
    const model = selectedModelRef.current;
    const planMode = isPlanModeRef.current;
    const tddMode = isTddModeRef.current;

    firePluginHook('chat:send', { text, model, planMode, tddMode });
    addMessage({ role: 'user', content: text });
    saveToStorage();
    setStreamError(null);

    addMessage({ role: 'assistant', content: '' });
    setStreaming(true);
    startElapsedTimer();

    let assistantContent = '';
    const abortController = new AbortController();
    abortRef.current = abortController;

    const updatedMessages = useChatStore.getState().messages;

    let errorMessage: string | null = null;
    await streamChatCompletion(
      {
        model,
        messages: updatedMessages,
        stream: true,
        agent_mode: true,
        plan_mode: planMode,
        tdd_mode: tddMode,
        web_search: webSearch,
        code_mode: codeMode,
        mcp_servers: mcpEnabled ? ['codebase-memory-mcp'] : [],
      },
      {
        onChunk: (chunk: string) => {
          assistantContent += chunk;
          appendToCurrentAssistantContent(chunk);
        },
        onDone: () => {},
        onError: (err: Error) => {
          if (err.name !== 'AbortError') {
            errorMessage = err.message;
          }
        },
      },
      abortController.signal,
    );

    updateLastAssistantMessage(assistantContent);
    saveToStorage();
    setStreaming(false);
    stopElapsedTimer();
    abortRef.current = null;

    if (errorMessage) {
      setStreamError(errorMessage);
    } else {
      detectChangesFromAssistantContent(assistantContent).catch(() => {});
    }

    // Flush queued messages (Codex-style: sends after agent finishes)
    const next = queueRef.current.shift();
    setQueuedMessages([...queueRef.current]);
    if (next !== undefined) {
      void runRef.current(next);
    }
  }, [
    addMessage, saveToStorage, setStreaming, appendToCurrentAssistantContent,
    updateLastAssistantMessage, startElapsedTimer, stopElapsedTimer,
    webSearch, codeMode, mcpEnabled,
  ]);

  useEffect(() => {
    runRef.current = runCompletion;
  }, [runCompletion]);

  const handleSend = useCallback(async (textToSend?: string) => {
    const text = textToSend ?? inputText;
    if (!text.trim()) return;

    if (useChatStore.getState().isStreaming) {
      queueRef.current = [...queueRef.current, text.trim()];
      setQueuedMessages([...queueRef.current]);
      setInputText('');
      if (textareaRef.current) textareaRef.current.style.height = 'auto';
      addToast('에이전트 작업이 끝나면 자동으로 전송됩니다.', 'info');
      return;
    }

    setInputText('');
    setActionMenuOpen(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    await runCompletion(text.trim());
  }, [inputText, runCompletion, addToast]);

  const handleSendNow = useCallback((index: number) => {
    const item = queueRef.current[index];
    if (item === undefined) return;
    queueRef.current = queueRef.current.filter((_, i) => i !== index);
    setQueuedMessages([...queueRef.current]);
    if (!useChatStore.getState().isStreaming) {
      void runCompletion(item);
    } else {
      queueRef.current = [item, ...queueRef.current];
      setQueuedMessages([...queueRef.current]);
    }
  }, [runCompletion]);

  const handleEditQueued = useCallback((index: number) => {
    const item = queueRef.current[index];
    if (item === undefined) return;
    queueRef.current = queueRef.current.filter((_, i) => i !== index);
    setQueuedMessages([...queueRef.current]);
    setInputText(item);
    textareaRef.current?.focus();
  }, []);

  const handleDeleteQueued = useCallback((index: number) => {
    queueRef.current = queueRef.current.filter((_, i) => i !== index);
    setQueuedMessages([...queueRef.current]);
  }, []);

  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
    stopElapsedTimer();
    addToast('생성이 중단되었습니다.', 'info');
  }, [setStreaming, addToast, stopElapsedTimer]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setInputText(prev => prev ? `${prev}\n[첨부 파일: ${file.name}]` : `[첨부 파일: ${file.name}] `);
    addToast(`파일 첨부: ${file.name}`, 'info');
  };

  // Close menus on click outside
  useEffect(() => {
    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.model-selector-wrap')) setModelDropdownOpen(false);
      if (!target.closest('.codex-action-plus-wrap')) setActionMenuOpen(false);
      if (!target.closest('.codex-access-pill-wrap')) setAccessDropdownOpen(false);
      if (!target.closest('.agk-mcp-chip-wrap')) setMcpMenuOpen(false);
    };
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, []);

  const isHero = messages.length === 0;
  const sessionTitle = activeSession?.title || 'New Conversation';
  const modelLabel = availableModels.find(m => m.id === selectedModel)?.description
    || MODEL_LABELS[selectedModel]
    || selectedModel;

  const editorContent = previewVisible ? <ArtifactPreview /> : <CodeEditor />;
  const changesContent = (
    <ChangePanel
      visible={true}
      onClose={() => {
        setChangePanelVisible(false);
        setEnvTab('env');
      }}
    />
  );

  /* ─── Composer card (shared by hero & docked) ─────────────── */
  const composerCard = (
    <div className="agk-composer-card">
      {!isHero && (
        <div className="codex-context-header-bar docked">
          <div className="context-item">
            <span className="item-icon">📁</span>
            <span className="item-text">{workspaceContext.project_name}</span>
          </div>
          <div className="context-item">
            <span className="item-icon">🖥️</span>
            <span className="item-text">{workspaceContext.target}</span>
          </div>
          <div className="context-item">
            <span className="item-icon">⑂</span>
            <span className="item-text branch">{workspaceContext.branch}</span>
          </div>
        </div>
      )}

      <div className="agk-input-main-card">
        <textarea
          ref={textareaRef}
          id="chat-input"
          className="codex-textarea"
          placeholder="Ask anything, @ to mention, / for actions"
          rows={1}
          value={inputText}
          onChange={(e) => {
            setInputText(e.target.value);
            e.target.style.height = 'auto';
            e.target.style.height = `${Math.min(220, e.target.scrollHeight)}px`;
          }}
          onKeyDown={handleKeyDown}
          aria-label="메시지 입력"
        />

        {/* Chip toolbar row */}
        <div className="agk-chip-toolbar">
          <div className="agk-chip-group">
            {/* + attach */}
            <div className="codex-action-plus-wrap">
              <button
                type="button"
                className={`plus-action-circle-btn ${actionMenuOpen ? 'open' : ''}`}
                onClick={() => setActionMenuOpen(!actionMenuOpen)}
                title="옵션 및 파일 첨부"
                aria-label="옵션 및 파일 첨부"
              >
                +
              </button>
              {actionMenuOpen && (
                <div className="plus-popover-dropdown">
                  <button
                    type="button"
                    className="popover-row"
                    onClick={() => { fileInputRef.current?.click(); setActionMenuOpen(false); }}
                  >
                    <span>📎</span>
                    <span>파일 및 사진 첨부</span>
                  </button>
                  <button
                    type="button"
                    className="popover-row"
                    onClick={() => { addToast('전체 코드베이스 심층 RAG 분석 활성화', 'info'); setActionMenuOpen(false); }}
                  >
                    <span>🧠</span>
                    <span>코드베이스 전체 탐색</span>
                  </button>
                </div>
              )}
            </div>

            {/* 전체 액세스 (Approve-for-me equivalent) */}
            <div className="codex-access-pill-wrap">
              <button
                type="button"
                className={`access-chip ${accessMode === 'full_access' ? 'amber' : 'safe'}`}
                onClick={() => setAccessDropdownOpen(!accessDropdownOpen)}
              >
                <span className="chip-icon">{accessMode === 'full_access' ? '🛡️!' : '🔒'}</span>
                <span className="chip-label">
                  {accessMode === 'full_access' ? '전체 액세스' : '읽기 전용'}
                </span>
                <span className="chip-chevron">⌄</span>
              </button>
              {accessDropdownOpen && (
                <div className="access-dropdown-menu">
                  <div
                    className={`access-opt ${accessMode === 'full_access' ? 'selected' : ''}`}
                    onClick={() => handleToggleAccessMode('full_access')}
                  >
                    ✓ 전체 액세스 (Full Access)
                  </div>
                  <div
                    className={`access-opt ${accessMode === 'restricted' ? 'selected' : ''}`}
                    onClick={() => handleToggleAccessMode('restricted')}
                  >
                    🔒 읽기 전용 (Read Only)
                  </div>
                </div>
              )}
            </div>

            {/* Search toggle */}
            <button
              type="button"
              className={`tool-chip ${webSearch ? 'active' : ''}`}
              onClick={() => setWebSearch((v) => !v)}
              aria-pressed={webSearch}
              title="웹 검색 도구 사용"
            >
              <span className="chip-icon">🌐</span>
              <span className="chip-label">Search</span>
            </button>

            {/* Code toggle */}
            <button
              type="button"
              className={`tool-chip ${codeMode ? 'active' : ''}`}
              onClick={() => setCodeMode((v) => !v)}
              aria-pressed={codeMode}
              title="코드 인터프리터 사용"
            >
              <span className="chip-icon">‹/›</span>
              <span className="chip-label">Code</span>
            </button>

            {/* MCP selector */}
            <div className="agk-mcp-chip-wrap">
              <button
                type="button"
                className={`tool-chip ${mcpEnabled ? 'active' : ''}`}
                onClick={() => setMcpMenuOpen((v) => !v)}
                aria-pressed={mcpEnabled}
                title="MCP 서버"
              >
                <span className="chip-icon">⊞</span>
                <span className="chip-label">MCP</span>
                <span className="chip-chevron">⌄</span>
              </button>
              {mcpMenuOpen && (
                <div className="mcp-dropdown-menu">
                  <button
                    type="button"
                    className={`mcp-opt ${mcpEnabled ? 'selected' : ''}`}
                    onClick={() => { setMcpEnabled(true); setMcpMenuOpen(false); }}
                  >
                    <span>⊞ codebase-memory-mcp</span>
                    <span className="mcp-opt-status on">연결됨</span>
                  </button>
                  <button
                    type="button"
                    className="mcp-opt"
                    onClick={() => { setMcpEnabled(false); setMcpMenuOpen(false); }}
                  >
                    <span>비활성화</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="agk-chip-group">
            {/* Model selector pill */}
            <div className="model-selector-wrap codex-model-selector-wrap">
              <button
                type="button"
                className="model-pill-trigger"
                onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
                aria-label="모델 선택"
              >
                <span className="model-name-text">{modelLabel}</span>
                <span className="chevron-mini">⌄</span>
              </button>

              {modelDropdownOpen && (
                <div className="model-selection-popover">
                  <div className="popover-sec-title">모델 및 추론 강도</div>
                  {availableModels.length > 0
                    ? availableModels.slice(0, 8).map(m => (
                      <div
                        key={m.id}
                        className={`model-choice-row ${m.id === selectedModel ? 'selected' : ''}`}
                        onClick={() => { setSelectedModel(m.id); setModelDropdownOpen(false); }}
                      >
                        <span>{m.description || m.id}</span>
                        {m.id === selectedModel && <span className="tag-recommended">현재 선택</span>}
                      </div>
                    ))
                    : (
                      <>
                        <div
                          className="model-choice-row selected"
                          onClick={() => { setSelectedModel('codex-5.6-sol-high'); setModelDropdownOpen(false); }}
                        >
                          <span>5.6 Sol High</span>
                          <span className="tag-recommended">현재 선택</span>
                        </div>
                        <div
                          className="model-choice-row"
                          onClick={() => { setSelectedModel('qwen-3.8-27b-gguf'); setModelDropdownOpen(false); }}
                        >
                          <span>Qwen 3.8 27B GGUF</span>
                        </div>
                        <div
                          className="model-choice-row"
                          onClick={() => { setSelectedModel('gemma-4-27b'); setModelDropdownOpen(false); }}
                        >
                          <span>Gemma 4 27B</span>
                        </div>
                        <div
                          className="model-choice-row"
                          onClick={() => { setSelectedModel('llama-3.2-mlx'); setModelDropdownOpen(false); }}
                        >
                          <span>Llama 3.2 3B MLX</span>
                        </div>
                      </>
                    )}
                </div>
              )}
            </div>

            {/* Mic */}
            <button
              type="button"
              className="mic-action-btn"
              onClick={() => addToast('음성 입력이 활성화되었습니다.', 'info')}
              title="음성 입력"
              aria-label="음성 입력"
            >
              🎙️
            </button>

            {/* Send / Stop */}
            {isStreaming ? (
              <button
                type="button"
                className="soundwave-circle-btn stop send-btn"
                onClick={handleStop}
                title="중단"
                aria-label="생성 중단"
              >
                ⏹
              </button>
            ) : (
              <button
                type="button"
                className={`soundwave-circle-btn ${inputText.trim() ? 'send-mode' : ''} send-btn`}
                onClick={() => handleSend()}
                title={inputText.trim() ? '전송' : '음성 대화 시작'}
                aria-label={inputText.trim() ? '메시지 전송' : '음성 대화 시작'}
              >
                {inputText.trim() ? '↑' : 'ılı'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className={`agk-workspace ${isHero ? 'is-empty' : ''}`}>
      {/* ── Main column: topbar + canvas + composer ──────────── */}
      <div className="agk-main-column">
        <header className="agk-topbar">
          <div className="agk-breadcrumb">
            <span className="crumb-project">antigravity-k</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-title">{sessionTitle}</span>
          </div>
          <div className="agk-topbar-actions">
            <button
              type="button"
              className="topbar-tool-btn"
              aria-label="채팅 히스토리"
              title="채팅 히스토리"
              onClick={() => setHistoryVisible(true)}
            >
              🕓
            </button>
            <button
              type="button"
              className="open-ide-btn"
              onClick={() => { setEnvPanelOpen(true); setEnvTab('code'); }}
              title="에디터 열기"
            >
              <span className="open-ide-icon">◤</span>
              Open IDE
            </button>
            <button
              type="button"
              className={`topbar-tool-btn ${envPanelOpen ? 'active' : ''}`}
              onClick={() => setEnvPanelOpen((v) => !v)}
              title="환경 패널 토글"
              aria-label="환경 패널 토글"
            >
              ◫
            </button>
            <button
              type="button"
              className="topbar-tool-btn"
              onClick={() => {
                if (document.fullscreenElement) {
                  document.exitFullscreen().catch(() => {});
                } else {
                  document.documentElement.requestFullscreen().catch(() => {});
                }
              }}
              title="전체화면"
              aria-label="전체화면"
            >
              □
            </button>
          </div>
        </header>

        <div className="agk-canvas">
          {!isHero && (
            <div className="agk-feed" ref={feedRef}>
              <div className="agk-feed-inner">
                {messages.map(msg => (
                  <ChatMessage key={msg.id ?? `${msg.role}:${msg.content}`} message={msg} />
                ))}
                {isStreaming && <WorkingIndicator elapsed={elapsed} />}
                {streamError && !isStreaming && (
                  <StreamErrorBanner
                    message={`exceeded retry limit — ${streamError}`}
                    onRetry={() => {
                      const lastUser = [...messages].reverse().find(m => m.role === 'user');
                      setStreamError(null);
                      if (lastUser) void runCompletion(lastUser.content);
                    }}
                  />
                )}
                {!isStreaming && (
                  <FileEditCard
                    onReview={() => { setEnvPanelOpen(true); setEnvTab('changes'); }}
                    onDiscard={() => {
                      const { rejectAll, clearChanges } = useChangeStore.getState();
                      rejectAll();
                      clearChanges();
                      addToast('편집 변경 사항을 실행 취소했습니다.', 'info');
                    }}
                  />
                )}
              </div>
            </div>
          )}

          {isHero && (
            <div className="unsloth-hero-head">
              <span className="hero-mascot" aria-hidden="true">🦥</span>
              <h1 className="hero-headline" data-testid="hero-headline">
                <mark className="hero-mark">Ready</mark> when you are
              </h1>
              <p className="hero-subline">Ssak-Ai에서 무엇이든 물어보세요 — 코드 작성, 파일 편집, 웹 검색을 도와드립니다.</p>
            </div>
          )}

          {/* Composer zone: queued card + composer */}
          <div className={`agk-composer-zone ${isHero ? 'hero' : 'docked'}`}>
            <QueuedMessagesCard
              items={queuedMessages}
              collapsed={queueCollapsed}
              onToggleCollapse={() => setQueueCollapsed((v) => !v)}
              onSendNow={handleSendNow}
              onEdit={handleEditQueued}
              onDelete={handleDeleteQueued}
            />
            {composerCard}
            {isHero && (
              <div
                className="codex-suggested-prompt-line hero-variant"
                onClick={() => {
                  setInputText('Make the two new orchestrator-swarm benchmarks prove real agent work');
                  textareaRef.current?.focus();
                }}
              >
                <span className="github-cat-icon">🐙</span>
                <span className="prompt-line-text">
                  Make the two new orchestrator-swarm benchmarks prove real agent work
                </span>
              </div>
            )}
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          onChange={handleFileUpload}
        />
      </div>

      {/* ── Right: Antigravity 환경 rail ──────────────────────── */}
      <EnvironmentPanel
        open={envPanelOpen}
        tab={envTab}
        onTabChange={setEnvTab}
        onClose={() => setEnvPanelOpen(false)}
        branch={workspaceContext.branch}
        editorContent={editorContent}
        changesContent={changesContent}
      />

      <ChatHistory visible={historyVisible} onClose={() => setHistoryVisible(false)} />

      {/* Screen-reader hint for pending review count */}
      <span className="visually-hidden" aria-live="polite">
        {pendingChangeCount > 0 ? `검토 대기 변경 ${pendingChangeCount}건` : ''}
      </span>
    </div>
  );
};

export default ChatPage;
