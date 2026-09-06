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

import React, { useEffect, useMemo, useRef, useCallback, useState } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { useProjectStore } from '../../stores/projectStore';
import { useUiStore } from '../../stores/uiStore';
import { useEditorStore } from '../../stores/editorStore';
import { useChangeStore } from '../../stores/changeStore';
import { useFileStore } from '../../stores/fileStore';
import {
  streamChatCompletion,
  ConversationRevisionConflictError,
  fetchConversationHistory,
  compactConversation,
  fetchModels,
  fetchLocalModels,
  loadModel,
  type ModelInfo,
  type LocalModelItem,
} from '../../api/client';
import { QuantBadge } from '../shared';
import {
  WorkspaceContextSchema,
  AccessModeResponseSchema,
  McpServersResponseSchema,
  type McpServerItem,
} from '../../api/clientSchema';
import { useEventWebSocket } from '../../hooks/useEventWebSocket';
import { detectChangesFromAssistantContent, registerFileModification } from '../../utils/changeDetector';
import { firePluginHook } from '../../plugin/pluginRegistry';
import ChatMessage from './ChatMessage';
import ChatHistory from './ChatHistory';
import ActivityTimeline from './ActivityTimeline';
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
import { useActivityStore } from '../../stores/activityStore';
import {
  createProjectIdentityHeaders,
  isIdentityCurrent,
  withProjectIdentitySearchParams,
} from '../../api/projectIdentity';

export const ChatPage: React.FC = () => {
  const {
    messages, isStreaming, selectedModel, isPlanMode, isTddMode,
    activeSession, activeSessionId, updateSessionTitle,
    addMessage, updateLastAssistantMessage, saveToStorage,
    conversationRevision, setConversationRevision, applyServerSnapshot,
    setStreaming, appendToCurrentAssistantContent, setCurrentAssistantContent,
    loadFromStorage, setSelectedModel, clearForProjectSwitch,
  } = useChatStore();

  const { addToast, setCommandPaletteVisible } = useUiStore();
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const activeProjectName = useProjectStore((s) => s.activeProjectName);
  const activeProjectPath = useProjectStore((s) => s.activeProjectPath);
  const switchEpoch = useProjectStore((s) => s.switchEpoch);
  const hydrateProjects = useProjectStore((s) => s.hydrateFromServer);
  const projectSwitchEpochRef = useRef(switchEpoch);
  const { previewVisible, openFile, clearForProjectSwitch: clearEditorForProjectSwitch } = useEditorStore();
  const { setPanelVisible: setChangePanelVisible, clearChanges } = useChangeStore();
  const pendingChangeCount = useChangeStore((s) => s.changes.filter((c) => c.status === 'pending').length);

  /* ─── States ─────────────────────────────────────────────── */
  const [inputText, setInputText] = useState<string>('');
  const [queuedMessages, setQueuedMessages] = useState<string[]>([]);
  const [queueCollapsed, setQueueCollapsed] = useState<boolean>(false);

  const [actionMenuOpen, setActionMenuOpen] = useState<boolean>(false);
  const [modelDropdownOpen, setModelDropdownOpen] = useState<boolean>(false);
  const [accessDropdownOpen, setAccessDropdownOpen] = useState<boolean>(false);
  const [mcpMenuOpen, setMcpMenuOpen] = useState<boolean>(false);
  const [mcpServerList, setMcpServerList] = useState<McpServerItem[]>([]);
  const [selectedMcp, setSelectedMcp] = useState<string[] | null>(null);
  const [webSearch, setWebSearch] = useState<boolean>(false);
  const [codeMode, setCodeMode] = useState<boolean>(false);
  const [accessMode, setAccessMode] = useState<'full_access' | 'restricted'>('full_access');

  const [envPanelOpen, setEnvPanelOpen] = useState<boolean>(true);
  const [isEditingTitle, setIsEditingTitle] = useState<boolean>(false);
  const [titleInput, setTitleInput] = useState<string>('');
  const [envTab, setEnvTab] = useState<EnvPanelTab>('env');
  const [historyVisible, setHistoryVisible] = useState<boolean>(false);

  const [streamError, setStreamError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number>(0);

  const [workspaceContext, setWorkspaceContext] = useState({
    project_name: 'Ssak-Ai',
    workspace_path: '.',
    target: '로컬',
    branch: 'codex/m1-task-events',
  });

  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [localModels, setLocalModels] = useState<LocalModelItem[]>([]);
  const [isScanningLocal, setIsScanningLocal] = useState<boolean>(false);

  const loadLocalModels = useCallback(async (refresh = false) => {
    setIsScanningLocal(true);
    try {
      const res = await fetchLocalModels(refresh);
      if (res.ok && res.models) {
        setLocalModels(res.models);
        const currentSelected = useChatStore.getState().selectedModel;
        const exists = res.models.some(m => m.id === currentSelected);
        if (!exists && res.models.length > 0) {
          const nextModel = res.recommended_default || res.models[0].id;
          setSelectedModel(nextModel);
        }
      }
    } catch (err) {
      console.error('Local model fetch error:', err);
    } finally {
      setIsScanningLocal(false);
    }
  }, [setSelectedModel]);

  const handleModelChoice = useCallback((modelId: string) => {
    setSelectedModel(modelId);
    setModelDropdownOpen(false);
    void loadModel(modelId).then((res) => {
      if (res.ok) {
        void loadLocalModels(false);
      }
    }).catch((err) => {
      console.warn('Background model load failed:', err);
    });
  }, [setSelectedModel, loadLocalModels]);

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
    void loadLocalModels(false);
    fetchModels()
      .then(models => setAvailableModels(models))
      .catch(() => {});

    // CTX-01: refresh/reconnect — align client projection to authoritative revision.
    const syncConversation = async () => {
      const chat = useChatStore.getState();
      const projectId = useProjectStore.getState().activeProjectId;
      const convId = chat.activeSessionId;
      if (!convId || !projectId) return;
      try {
        const history = await fetchConversationHistory(convId, projectId);
        useChatStore.getState().applyServerSnapshot({
          conversation_id: history.snapshot.conversation_id,
          revision: history.snapshot.revision,
          summary: history.snapshot.summary,
          retained_message_ids: history.snapshot.retained_message_ids,
          messages: history.messages.map((m) => ({
            id: m.id,
            role: m.role === "tool" ? "system" : m.role,
            content: m.content,
          })),
        });
      } catch {
        // Conversation may not exist yet on server — keep local projection.
      }
    };
    void syncConversation();
  }, [loadFromStorage, loadLocalModels]);

  const reloadWorkspaceContext = useCallback(() => {
    const store = useProjectStore.getState();
    const capturedEpoch = store.switchEpoch;
    setWorkspaceContext((prev) => ({
      ...prev,
      project_name: store.activeProjectName || prev.project_name,
      workspace_path: store.activeProjectPath || prev.workspace_path,
    }));
    fetch('/api/workspace/context', { headers: createProjectIdentityHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(raw => {
        if (!isIdentityCurrent(capturedEpoch)) return;
        if (raw) {
          const parsed = WorkspaceContextSchema.safeParse(raw);
          if (parsed.success) {
            const latest = useProjectStore.getState();
            setWorkspaceContext({
              project_name: latest.activeProjectName || parsed.data.project_name,
              workspace_path: latest.activeProjectPath || parsed.data.workspace_path || '.',
              target: parsed.data.target,
              branch: parsed.data.branch,
            });
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    void hydrateProjects();
  }, [hydrateProjects]);

  useEffect(() => {
    reloadWorkspaceContext();
    // 실행 권한 모드 초기값 동기화 (읽기 전용이면 칩이 즉시 반영됨)
    fetch('/api/system/access-mode', { headers: createProjectIdentityHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(raw => {
        if (raw) {
          const parsed = AccessModeResponseSchema.safeParse(raw);
          if (parsed.success && parsed.data.mode === 'read_only') {
            setAccessMode('restricted');
          }
        }
      })
      .catch(() => {});
    // 구성된 MCP 서버 실목록 (환경 레일 "소스"와 동일한 소스)
    fetch('/api/mcp/servers', { headers: createProjectIdentityHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(raw => {
        if (raw) {
          const parsed = McpServersResponseSchema.safeParse(raw);
          if (parsed.success && parsed.data.ok) {
            setMcpServerList(parsed.data.servers);
            setSelectedMcp(parsed.data.servers.map((s) => s.name));
            return;
          }
        }
        setSelectedMcp([]);
      })
      .catch(() => setSelectedMcp([]));
  }, [reloadWorkspaceContext]);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  const handleToggleAccessMode = async (mode: 'full_access' | 'restricted') => {
    try {
      await fetch('/api/system/access-mode', {
        method: 'POST',
        headers: createProjectIdentityHeaders({ 'Content-Type': 'application/json' }),
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
    onToolExecutionStarted: (data) => {
      useActivityStore.getState().recordToolStart(data);
    },
    onToolExecutionFinished: () => {
      useActivityStore.getState().recordToolEnd();
    },
    onFailureDetected: (data) => {
      useActivityStore.getState().recordError(data.error ?? data.message ?? '알 수 없는 오류');
    },
    onPlanningModeStarted: (data) => {
      useActivityStore.getState().recordPlan(data.goal ?? '');
    },
    onFileOpened: (data) => {
      const filePath = data?.filepath;
      if (filePath) {
        useActivityStore.getState().recordFileRead(filePath);
        const fileName = filePath.split(/[/\\]/).pop() || 'unknown';
        const capturedEpoch = useProjectStore.getState().switchEpoch;
        fetch(withProjectIdentitySearchParams(`/api/fs/read?file=${encodeURIComponent(filePath)}`), {
          headers: createProjectIdentityHeaders(),
        })
          .then(r => r.ok ? r.json() : null)
          .then(d => {
            if (!isIdentityCurrent(capturedEpoch)) return;
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
        useActivityStore.getState().recordFileEdit(filePath);
        const fileName = filePath.split(/[/\\]/).pop() || 'unknown';
        const capturedEpoch = useProjectStore.getState().switchEpoch;
        fetch(withProjectIdentitySearchParams(`/api/fs/read?file=${encodeURIComponent(filePath)}`), {
          headers: createProjectIdentityHeaders(),
        })
          .then(r => r.ok ? r.json() : null)
          .then(d => {
            if (!isIdentityCurrent(capturedEpoch)) return;
            if (d?.content !== undefined) {
              openFile(filePath, fileName, d.content);
            }
          })
          .catch(() => {});
        registerFileModification(filePath, fileName)
          .then((registered) => {
            if (!isIdentityCurrent(capturedEpoch)) return;
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

  /* ─── WS-04: project switch → cancel pending + reload context ─ */
  useEffect(() => {
    const prevEpoch = projectSwitchEpochRef.current;
    if (switchEpoch === prevEpoch) return;
    projectSwitchEpochRef.current = switchEpoch;

    const hadPending = Boolean(abortRef.current)
      || useChatStore.getState().isStreaming
      || queueRef.current.length > 0;
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    queueRef.current = [];
    setQueuedMessages([]);
    setStreaming(false);
    setCurrentAssistantContent('');
    setStreamError(null);
    stopElapsedTimer();
    useActivityStore.getState().clear();
    useActivityStore.getState().setSessionEnded();

    clearEditorForProjectSwitch();
    clearChanges();
    useFileStore.getState().clearForProjectSwitch();

    clearForProjectSwitch();
    loadFromStorage();
    if (useChatStore.getState().sessions.length === 0) {
      useChatStore.getState().createNewSession();
    }

    reloadWorkspaceContext();

    if (hadPending) {
      addToast('프로젝트 전환: 이전 요청을 취소하고 컨텍스트를 다시 불러왔습니다.', 'info');
    }
  }, [
    switchEpoch,
    clearForProjectSwitch,
    clearEditorForProjectSwitch,
    clearChanges,
    loadFromStorage,
    setStreaming,
    setCurrentAssistantContent,
    reloadWorkspaceContext,
    addToast,
    stopElapsedTimer,
  ]);

  /* ─── MCP allowlist (구성된 서버 기준 선택 집합) ─────────────── */
  const mcpAllowlist = useMemo(
    () => selectedMcp ?? [],
    [selectedMcp],
  );

  /* ─── Send / queue / run loop ────────────────────────────── */
  const runCompletion = useCallback(async (text: string) => {
    const model = selectedModelRef.current;
    const planMode = isPlanModeRef.current;
    const tddMode = isTddModeRef.current;
    const requestEpoch = useProjectStore.getState().switchEpoch;
    const requestProjectId = useProjectStore.getState().activeProjectId;

    firePluginHook('chat:send', { text, model, planMode, tddMode });
    useActivityStore.getState().clear();
    useActivityStore.getState().setSessionStarted();
    addMessage({ role: 'user', content: text });
    saveToStorage();
    setStreamError(null);

    addMessage({ role: 'assistant', content: '' });
    setStreaming(true);
    startElapsedTimer();

    let assistantContent = '';
    const abortController = new AbortController();
    abortRef.current = abortController;

    // CTX-01: client message array is projection only — server store is authoritative.

    let errorMessage: string | null = null;
    const expectedRevision = useChatStore.getState().conversationRevision ?? 0;
    const conversationId = useChatStore.getState().activeSessionId || activeSessionId;
    await streamChatCompletion(
      {
        model,
        // CTX-01: server store is SoT — send new turn + expected revision only
        messages: [{ role: 'user', content: text }],
        new_turn: { role: 'user', content: text },
        conversation_id: conversationId ?? undefined,
        conversation_revision: expectedRevision,
        use_conversation_store: true,
        stream: true,
        agent_mode: true,
        plan_mode: planMode,
        tdd_mode: tddMode,
        web_search: webSearch,
        code_mode: codeMode,
        mcp_servers: mcpAllowlist,
        // project_id / project_revision also injected by client.streamChatCompletion
        project_id: requestProjectId ?? undefined,
      },
      {
        onChunk: (chunk: string) => {
          if (!isIdentityCurrent(requestEpoch)) return;
          assistantContent += chunk;
          appendToCurrentAssistantContent(chunk);
        },
        onDone: () => {},
        onError: (err: Error) => {
          if (err.name === 'AbortError') return;
          if (err instanceof ConversationRevisionConflictError) {
            errorMessage = `stale_conversation_revision:${err.payload.current_revision}`;
            return;
          }
          errorMessage = err.message;
        },
        onConversationSnapshot: (snapshot) => {
          if (!isIdentityCurrent(requestEpoch)) return;
          applyServerSnapshot({
            conversation_id: snapshot.conversation_id,
            revision: snapshot.revision,
            summary: snapshot.summary,
            retained_message_ids: snapshot.retained_message_ids,
          });
        },
      },
      abortController.signal,
    );

    // Stale responses from a previous project must not merge into the new UI/store.
    if (!isIdentityCurrent(requestEpoch)) {
      if (abortRef.current === abortController) {
        abortRef.current = null;
      }
      return;
    }

    updateLastAssistantMessage(assistantContent);
    saveToStorage();
    setStreaming(false);
    stopElapsedTimer();
    abortRef.current = null;

    // Record session end + approximate token usage
    useActivityStore.getState().setSessionEnded();
    const approxPromptTokens = Math.ceil(text.length / 4);
    const approxCompletionTokens = Math.ceil(assistantContent.length / 4);
    useActivityStore.getState().recordTokenUsage(approxPromptTokens, approxCompletionTokens);

    if (errorMessage) {
      if (errorMessage.includes('revision') || errorMessage.includes('409')) {
        // Best-effort: refresh authoritative projection on conflict.
        try {
          const convId = useChatStore.getState().activeSessionId;
          const projectId = useProjectStore.getState().activeProjectId;
          if (convId) {
            const history = await fetchConversationHistory(convId, projectId);
            applyServerSnapshot({
              conversation_id: history.snapshot.conversation_id,
              revision: history.snapshot.revision,
              summary: history.snapshot.summary,
              retained_message_ids: history.snapshot.retained_message_ids,
              messages: history.messages.map((m) => ({
                id: m.id,
                role: m.role === 'tool' ? 'system' : m.role,
                content: m.content,
              })),
            });
            setStreamError(
              `대화 리비전이 충돌했습니다 (서버 r${history.snapshot.revision}). 최신 이력으로 동기화했습니다. 다시 전송해 주세요.`,
            );
          } else {
            setStreamError(errorMessage);
          }
        } catch {
          setStreamError(errorMessage);
        }
      } else {
        setStreamError(errorMessage);
      }
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
    webSearch, codeMode, mcpAllowlist,
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

  const handleClearAllQueued = useCallback(() => {
    queueRef.current = [];
    setQueuedMessages([]);
  }, []);

  const handleMoveUpQueued = useCallback((index: number) => {
    if (index <= 0) return;
    const items = [...queueRef.current];
    const temp = items[index];
    items[index] = items[index - 1];
    items[index - 1] = temp;
    queueRef.current = items;
    setQueuedMessages(items);
  }, []);

  const handleMoveDownQueued = useCallback((index: number) => {
    if (index >= queueRef.current.length - 1) return;
    const items = [...queueRef.current];
    const temp = items[index];
    items[index] = items[index + 1];
    items[index + 1] = temp;
    queueRef.current = items;
    setQueuedMessages(items);
  }, []);

  const handleReorderQueued = useCallback((fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return;
    const items = [...queueRef.current];
    const [moved] = items.splice(fromIndex, 1);
    items.splice(toIndex, 0, moved);
    queueRef.current = items;
    setQueuedMessages(items);
  }, []);

  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
    stopElapsedTimer();
    useActivityStore.getState().setSessionEnded();
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
  const modelLabel = useMemo(() => {
    const foundLocal = localModels.find(m => m.id === selectedModel);
    if (foundLocal) {
      const tag = foundLocal.parameter_count_b > 0
        ? ` (${foundLocal.parameter_count_b}B)`
        : foundLocal.disk_size_gb > 0
          ? ` (${foundLocal.disk_size_gb}GB)`
          : '';
      return `${foundLocal.name || foundLocal.id}${tag}`;
    }
    const foundAvail = availableModels.find(m => m.id === selectedModel);
    if (foundAvail) {
      return foundAvail.description || foundAvail.id;
    }
    if (selectedModel === 'default') {
      return localModels[0]?.name ? `${localModels[0].name} (로컬)` : '로컬 모델 감지 중...';
    }
    return selectedModel;
  }, [selectedModel, localModels, availableModels]);

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
          style={{
            color: 'var(--text-primary, #f0f6fc)',
            caretColor: 'var(--accent-color, #e5a93b)',
          }}
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

            {/* MCP selector — 구성된 서버 실목록 기반 */}
            <div className="agk-mcp-chip-wrap">
              <button
                type="button"
                className={`tool-chip ${mcpAllowlist.length > 0 ? 'active' : ''}`}
                onClick={() => setMcpMenuOpen((v) => !v)}
                aria-pressed={mcpAllowlist.length > 0}
                title="MCP 서버"
              >
                <span className="chip-icon">⊞</span>
                <span className="chip-label">MCP</span>
                <span className="chip-chevron">⌄</span>
              </button>
              {mcpMenuOpen && (
                <div className="mcp-dropdown-menu">
                  {mcpServerList.length === 0 ? (
                    <div className="mcp-opt mcp-empty-row">
                      <span>구성된 MCP 서버가 없습니다</span>
                      <span className="mcp-opt-status">.mcp.json</span>
                    </div>
                  ) : (
                    mcpServerList.map(server => {
                      const isSelected = mcpAllowlist.includes(server.name);
                      return (
                        <button
                          key={server.name}
                          type="button"
                          className={`mcp-opt ${isSelected ? 'selected' : ''}`}
                          onClick={() => {
                            setSelectedMcp(prev => {
                              const base = prev ?? mcpServerList.map(s => s.name);
                              return isSelected
                                ? base.filter(n => n !== server.name)
                                : [...base, server.name];
                            });
                          }}
                        >
                          <span>{isSelected ? '✓' : '○'} {server.name}</span>
                          <span className="mcp-opt-status on">{server.transport}</span>
                        </button>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="agk-chip-group">
            {/* Model selector pill */}
            <div className="model-selector-wrap codex-model-selector-wrap">
              <button
                type="button"
                className="model-pill-trigger model-select-trigger"
                onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
                aria-label="모델 선택"
              >
                <span className="model-name-text">{modelLabel}</span>
                <span className="chevron-mini">⌄</span>
              </button>

              {modelDropdownOpen && (
                <div className="model-selection-popover">
                  <div className="model-dropdown-header-row">
                    <span className="popover-sec-title">💻 본 PC 전체 로컬 모델 ({localModels.length}개)</span>
                    <button
                      type="button"
                      className="model-refresh-btn"
                      title="본 PC 로컬 모델 다시 검색"
                      disabled={isScanningLocal}
                      onClick={(e) => {
                        e.stopPropagation();
                        void loadLocalModels(true);
                      }}
                    >
                      {isScanningLocal ? '스캔 중...' : '↻ 재검색'}
                    </button>
                  </div>

                  {localModels.length === 0 ? (
                    <div className="model-empty-notice">
                      {isScanningLocal
                        ? '본 PC의 로컬 모델을 스캔하고 있습니다...'
                        : '본 PC에서 실행 중이거나 다운로드된 로컬 모델을 찾을 수 없습니다.'}
                    </div>
                  ) : (
                    <>
                      {/* 1. 실행 중 모델 (Ollama / Local APIs) */}
                      {localModels.filter((m) => m.status === 'running').length > 0 && (
                        <div className="model-group-section">
                          <div className="model-group-title">🟢 실행 중 모델 (즉시 추론 가능)</div>
                          {localModels
                            .filter((m) => m.status === 'running')
                            .map((m) => (
                              <div
                                key={m.id}
                                className={`model-choice-row ${m.id === selectedModel ? 'selected' : ''}`}
                                onClick={() => handleModelChoice(m.id)}
                              >
                                <div className="model-row-left">
                                  <div className="model-row-title-line">
                                    <span className="status-dot running" />
                                    <span className="model-name-text">{m.name || m.id}</span>
                                  </div>
                                  <div className="model-chip-badges">
                                    <span className="badge-provider">{m.provider}</span>
                                    {m.parameter_count_b > 0 && (
                                      <span className="badge-param">{m.parameter_count_b}B</span>
                                    )}
                                    {m.role && <span className="badge-role">{m.role}</span>}
                                  </div>
                                </div>
                                {m.id === selectedModel && <span className="tag-recommended">현재 선택</span>}
                              </div>
                            ))}
                        </div>
                      )}

                      {/* 2. 다운로드/캐시된 Unsloth 및 로컬 GGUF 모델 */}
                      {localModels.filter((m) => m.status !== 'running' && m.provider === 'unsloth').length > 0 && (
                        <div className="model-group-section">
                          <div className="model-group-title">🦥 Unsloth 다운로드 모델 (GGUF)</div>
                          {localModels
                            .filter((m) => m.status !== 'running' && m.provider === 'unsloth')
                            .map((m) => (
                              <div
                                key={m.id}
                                className={`model-choice-row ${m.id === selectedModel ? 'selected' : ''}`}
                                onClick={() => handleModelChoice(m.id)}
                              >
                                <div className="model-row-left">
                                  <div className="model-row-title-line">
                                    <span className="status-dot cached" />
                                    <span className="model-name-text">{m.name || m.id}</span>
                                  </div>
                                  <div className="model-chip-badges">
                                    <span className="badge-provider unsloth">UNSLOTH</span>
                                    {m.disk_size_gb > 0 && (
                                      <span className="badge-disk">{m.disk_size_gb} GB</span>
                                    )}
                                    {m.quantization && (
                                      <QuantBadge quantization={m.quantization} variant="chip" />
                                    )}
                                    {m.role && <span className="badge-role">{m.role}</span>}
                                  </div>
                                </div>
                                {m.id === selectedModel && <span className="tag-recommended">현재 선택</span>}
                              </div>
                            ))}
                        </div>
                      )}

                      {/* 3. 기타 로컬/MLX/HuggingFace 모델 */}
                      {localModels.filter((m) => m.status !== 'running' && m.provider !== 'unsloth').length > 0 && (
                        <div className="model-group-section">
                          <div className="model-group-title">📦 MLX / 로컬 캐시 모델</div>
                          {localModels
                            .filter((m) => m.status !== 'running' && m.provider !== 'unsloth')
                            .map((m) => (
                              <div
                                key={m.id}
                                className={`model-choice-row ${m.id === selectedModel ? 'selected' : ''}`}
                                onClick={() => handleModelChoice(m.id)}
                              >
                                <div className="model-row-left">
                                  <div className="model-row-title-line">
                                    <span className="status-dot cached" />
                                    <span className="model-name-text">{m.name || m.id}</span>
                                  </div>
                                  <div className="model-chip-badges">
                                    <span className={`badge-provider ${m.provider}`}>{m.provider}</span>
                                    {m.disk_size_gb > 0 && (
                                      <span className="badge-disk">{m.disk_size_gb} GB</span>
                                    )}
                                    {m.quantization && (
                                      <QuantBadge quantization={m.quantization} variant="chip" />
                                    )}
                                    {m.role && <span className="badge-role">{m.role}</span>}
                                  </div>
                                </div>
                                {m.id === selectedModel && <span className="tag-recommended">현재 선택</span>}
                              </div>
                            ))}
                        </div>
                      )}
                    </>
                  )}

                  {/* ── Optional Cloud / Fallback Models Section ── */}
                  {availableModels.filter((m) => !m.is_local && !localModels.some((lm) => lm.id === m.id)).length > 0 && (
                    <>
                      <div className="model-dropdown-divider" />
                      <div className="popover-sec-title subhead">☁️ 외부 / 클라우드 모델</div>
                      {availableModels
                        .filter((m) => !m.is_local && !localModels.some((lm) => lm.id === m.id))
                        .slice(0, 8)
                        .map((m) => (
                          <div
                            key={m.id}
                            className={`model-choice-row ${m.id === selectedModel ? 'selected' : ''}`}
                            onClick={() => {
                              setSelectedModel(m.id);
                              setModelDropdownOpen(false);
                            }}
                          >
                            <span>{m.description || m.id}</span>
                            {m.id === selectedModel && <span className="tag-recommended">현재 선택</span>}
                          </div>
                        ))}
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
            <span className="crumb-project" data-testid="active-project-label" data-project-id={activeProjectId ?? ''}>
              {activeProjectName || workspaceContext?.project_name || 'Ssak-Ai'}
            </span>
            <span className="crumb-sep">/</span>
            {isEditingTitle ? (
              <input
                type="text"
                className="crumb-title-input"
                value={titleInput}
                autoFocus
                onChange={(e) => setTitleInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (titleInput.trim() && activeSessionId) {
                      updateSessionTitle(activeSessionId, titleInput.trim());
                      addToast('대화 제목이 변경되었습니다.', 'info');
                    }
                    setIsEditingTitle(false);
                  } else if (e.key === 'Escape') {
                    setIsEditingTitle(false);
                  }
                }}
                onBlur={() => {
                  if (titleInput.trim() && activeSessionId) {
                    updateSessionTitle(activeSessionId, titleInput.trim());
                  }
                  setIsEditingTitle(false);
                }}
              />
            ) : (
              <span
                className="crumb-title editable"
                title="클릭하여 대화 제목 수정"
                onClick={() => {
                  setIsEditingTitle(true);
                  setTitleInput(sessionTitle);
                }}
              >
                {sessionTitle}
                <span className="crumb-edit-icon" aria-hidden="true">✎</span>
              </span>
            )}
          </div>
          <div className="agk-topbar-actions">
            <button
              type="button"
              className="topbar-tool-btn"
              aria-label="명령 팔레트 열기 (Cmd+K)"
              title="명령 팔레트 (Cmd+K)"
              onClick={() => setCommandPaletteVisible(true)}
            >
              ⌘
            </button>
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
                <ActivityTimeline />
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
              onMoveUp={handleMoveUpQueued}
              onMoveDown={handleMoveDownQueued}
              onReorder={handleReorderQueued}
              onClearAll={handleClearAllQueued}
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
        workspacePath={workspaceContext.workspace_path}
        mcpServers={mcpServerList}
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
