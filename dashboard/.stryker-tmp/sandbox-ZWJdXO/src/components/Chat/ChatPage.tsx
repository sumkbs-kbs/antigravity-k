/**
 * ChatPage — Main chat interface with IDE layout
 * ================================================
 * Integrates FileExplorer, Editor, ArtifactPreview, and Chat components
 * in a 3-panel IDE layout.
 */
// @ts-nocheck


import React, { useEffect, useRef, useCallback } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { useUiStore } from '../../stores/uiStore';
import { useEditorStore } from '../../stores/editorStore';
import { useChangeStore } from '../../stores/changeStore';
import { streamChatCompletion } from '../../api/client';
import { useEventWebSocket } from '../../hooks/useEventWebSocket';
import { detectChangesFromAssistantContent, registerFileModification } from '../../utils/changeDetector';
import { firePluginHook } from '../../plugin/pluginRegistry';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import ChatHistory from './ChatHistory';
import ModelSelector from './ModelSelector';
import PlanToggleBar from './PlanToggleBar';
import EmptyState from './EmptyState';
import FileExplorer from '../Editor/FileExplorer';
import CodeEditor from '../Editor/Editor';
import ArtifactPreview from '../Editor/ArtifactPreview';
import ChangePanel from '../Editor/ChangePanel';
import SplitPane from '../Layout/SplitPane';

const ChatPage: React.FC = () => {
  const {
    messages, isStreaming, selectedModel, isPlanMode, isTddMode,
    addMessage, updateLastAssistantMessage, saveToStorage,
    setStreaming, appendToCurrentAssistantContent,
    createNewSession, loadFromStorage,
  } = useChatStore();

  const { setChatHistoryVisible, chatHistoryVisible, addToast } = useUiStore();
  const { previewVisible, openFile } = useEditorStore();
  const abortRef = useRef<AbortController | null>(null);
  const chatHistoryRef = useRef<HTMLDivElement>(null);
  const toolIndicatorRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Use refs to avoid stale closures in async callbacks
  const selectedModelRef = useRef(selectedModel);
  selectedModelRef.current = selectedModel;
  const isPlanModeRef = useRef(isPlanMode);
  isPlanModeRef.current = isPlanMode;
  const isTddModeRef = useRef(isTddMode);
  isTddModeRef.current = isTddMode;

  const { panelVisible: changePanelVisible, setPanelVisible: setChangePanelVisible } = useChangeStore();
  const pendingChangeCount = useChangeStore((s) => s.changes.filter((c) => c.status === 'pending').length);

  // ─── Load chat history from localStorage on mount ────────────────
  useEffect(() => {
    loadFromStorage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Scroll to bottom on new messages ────────────────────────────
  useEffect(() => {
    if (chatHistoryRef.current) {
      chatHistoryRef.current.scrollTop = chatHistoryRef.current.scrollHeight;
    }
  }, [messages]);

  // ─── Listen for approval & wiki-ref events ──────────────────────
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      const text = e.detail?.text;
      if (text && inputRef.current) {
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype, 'value'
        )?.set;
        nativeInputValueSetter?.call(inputRef.current, text);
        inputRef.current.dispatchEvent(new Event('input', { bubbles: true }));
        // Auto-send after brief delay
        setTimeout(() => {
          const sendBtn = document.querySelector('.glow-btn') as HTMLButtonElement;
          sendBtn?.click();
        }, 100);
      }
    };

    const wikiRefHandler = (e: CustomEvent) => {
      const text = e.detail?.text;
      if (text && inputRef.current) {
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype, 'value'
        )?.set;
        nativeInputValueSetter?.call(inputRef.current, text);
        inputRef.current.dispatchEvent(new Event('input', { bubbles: true }));
        inputRef.current.focus();
      }
    };

    window.addEventListener('agk:approval-response', handler as EventListener);
    window.addEventListener('agk:wiki-ref', wikiRefHandler as EventListener);
    return () => {
      window.removeEventListener('agk:approval-response', handler as EventListener);
      window.removeEventListener('agk:wiki-ref', wikiRefHandler as EventListener);
    };
  }, []);

  // ─── Get the last assistant bubble for tool event injection ──────
  const getLastAssistantBubble = useCallback((): HTMLElement | null => {
    const historyEl = chatHistoryRef.current;
    if (!historyEl) return null;
    const lastMsg = historyEl.lastElementChild;
    if (!lastMsg?.classList.contains('assistant')) return null;
    return lastMsg.querySelector('.bubble') as HTMLElement;
  }, []);

  // ─── Event WebSocket with full agent event handling ──────────────
  useEventWebSocket({
    onModeChanged: (data) => {
      const mode = data?.to_mode;
      if (mode) addToast(`🔄 모드 전환: ${mode.toUpperCase()}`, 'info');
    },
    onToolExecutionStarted: (data) => {
      const bubble = getLastAssistantBubble();
      if (!bubble) return;
      const toolName = data?.name || data?.tool_name || 'unknown_tool';
      if (toolIndicatorRef.current?.parentNode) toolIndicatorRef.current.remove();

      const div = document.createElement('div');
      div.className = 'tool-timeline-badge start';
      div.style.marginTop = '8px';
      div.innerHTML = `<span class="icon">⚙️</span> <span class="text">Running Tool <b style="color:var(--accent-color);">${toolName}</b>... <span class="typing-indicator" style="height:12px;margin-left:4px;"><span></span><span></span><span></span></span></span>`;
      bubble.appendChild(div);
      toolIndicatorRef.current = div;
      if (chatHistoryRef.current) chatHistoryRef.current.scrollTop = chatHistoryRef.current.scrollHeight;
    },
    onToolExecutionFinished: () => {
      if (toolIndicatorRef.current?.parentNode) {
        toolIndicatorRef.current.remove();
        toolIndicatorRef.current = null;
      }
    },
    onFailureDetected: () => {
      const bubble = getLastAssistantBubble();
      if (!bubble) return;
      const div = document.createElement('div');
      div.className = 'tool-timeline-badge error';
      div.style.marginTop = '8px';
      div.innerHTML = `<span class="icon">⚠️</span> <span class="text"><b>Failure Detected:</b> Agent is attempting to recover...</span>`;
      bubble.appendChild(div);
      if (chatHistoryRef.current) chatHistoryRef.current.scrollTop = chatHistoryRef.current.scrollHeight;
      if (toolIndicatorRef.current?.parentNode) toolIndicatorRef.current.remove();
    },
    onCognitiveAdaptation: () => {
      const bubble = getLastAssistantBubble();
      if (!bubble) return;
      const div = document.createElement('div');
      div.style.marginTop = '8px';
      div.innerHTML = `<span class="agent-badge adapting">ADAPTING</span> <span style="font-size: 13px; color: var(--warning);">동적 전략 수정 중...</span>`;
      bubble.appendChild(div);
      if (chatHistoryRef.current) chatHistoryRef.current.scrollTop = chatHistoryRef.current.scrollHeight;
    },
    onPlanningModeStarted: () => {
      const bubble = getLastAssistantBubble();
      if (!bubble) return;
      const div = document.createElement('div');
      div.style.marginTop = '8px';
      div.innerHTML = `<span class="agent-badge planning">PLANNING</span> <span style="font-size: 13px; color: var(--accent-color);">실행 계획 수립 중...</span>`;
      bubble.appendChild(div);
      if (chatHistoryRef.current) chatHistoryRef.current.scrollTop = chatHistoryRef.current.scrollHeight;
    },
    onFileOpened: (data) => {
      const filePath = data?.filepath;
      if (filePath) {
        const fileName = filePath.split(/[/\\]/).pop() || 'unknown';
        // Load and open in editor
        fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`)
          .then(r => r.json())
          .then(d => {
            if (d.content !== undefined) {
              openFile(filePath, fileName, d.content);
            }
          })
          .catch(() => {});
      }
    },
    onFileModified: (data) => {
      const filePath = data?.filepath;
      if (filePath) {
        const fileName = filePath.split(/[/\\]/).pop() || 'unknown';
        // Open file in editor
        fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`)
          .then(r => r.json())
          .then(d => {
            if (d.content !== undefined) {
              openFile(filePath, fileName, d.content);
            }
          })
          .catch(() => {});
        // Register change in Change Store for review
        registerFileModification(filePath, fileName)
          .then((registered) => {
            if (registered) {
              addToast(`📋 변경 감지: ${fileName}`, 'info');
            }
          })
          .catch(() => {});
      }
    },
  });

  // ─── Handle sending messages ─────────────────────────────────────
  const handleSend = useCallback(async (text: string, imageDataUrl?: string) => {
    if (!text && !imageDataUrl) return;

    const model = selectedModelRef.current;
    const planMode = isPlanModeRef.current;
    const tddMode = isTddModeRef.current;

    let userContent: string | any[] = text;
    let displayText = text;

    if (imageDataUrl) {
      userContent = [
        { type: 'text', text: text || '이 이미지를 분석해주세요.' },
        { type: 'image_url', image_url: { url: imageDataUrl } },
      ];
      displayText = text + ' 📎🖼️';
    }

    firePluginHook('chat:send', { text, model, planMode, tddMode });
    addMessage({ role: 'user', content: displayText });
    saveToStorage();
    addMessage({ role: 'assistant', content: '' });
    setStreaming(true);

    let assistantContent = '';
    const abortController = new AbortController();
    abortRef.current = abortController;

    const updatedMessages = useChatStore.getState().messages;
    await streamChatCompletion(
      { model, messages: updatedMessages, stream: true, agent_mode: true, plan_mode: planMode, tdd_mode: tddMode },
      (chunk) => {
        assistantContent += chunk;
        appendToCurrentAssistantContent(chunk);
        updateLastAssistantMessage(assistantContent);
        saveToStorage();
      },
      () => {
        // Update final message
        updateLastAssistantMessage(assistantContent);
        saveToStorage();
        setStreaming(false);
        abortRef.current = null;
        firePluginHook('chat:response', { content: assistantContent, model: selectedModelRef.current });

        // ── Auto-detect file changes from assistant response ──
        if (assistantContent && assistantContent.length > 50) {
          detectChangesFromAssistantContent(assistantContent)
            .then(count => {
              if (count > 0) {
                addToast(`📋 ${count}개 파일 변경 감지 — 검토해보세요`, 'info');
              }
            })
            .catch(() => {});
        }
      },
      (err) => {
        console.error('Stream error:', err);
        updateLastAssistantMessage(assistantContent || `Error: ${err.message}`);
        saveToStorage();
        setStreaming(false);
        abortRef.current = null;
        addToast(`오류: ${err.message}`, 'error');
      },
      abortController.signal
    );
  }, []);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
  }, [setStreaming]);

  const handleExampleClick = useCallback((text: string) => {
    handleSend(text);
  }, [handleSend]);

  // Register input ref with ChatInput via window callback
  const registerInput = useCallback((el: HTMLTextAreaElement | null) => {
    inputRef.current = el;
  }, []);

  return (
    <div className="ide-layout">
      <SplitPane
        direction="horizontal"
        storageKey="agk_ide_split_sizes"
        initialSizes={[20, 40, 40]}
        minSizes={[180, 240, 280]}
        gutterSize={6}
      >
        {/* Left: File Explorer */}
        <div className="ide-explorer glass-panel" style={{ borderRight: 'none', height: '100%' }}>
          <FileExplorer />
        </div>

        {/* Center: Editor / Preview / Changes */}
        <div className="flex flex-col" style={{ minWidth: 0, overflow: 'hidden', height: '100%' }}>
          {changePanelVisible ? (
            <ChangePanel
              visible={changePanelVisible}
              onClose={() => setChangePanelVisible(false)}
            />
          ) : previewVisible ? (
            <ArtifactPreview />
          ) : (
            <CodeEditor />
          )}
        </div>

        {/* Right: AI Chat */}
        <div className="ide-chat" style={{ height: '100%' }}>
          <div className="chat-container">
          <div className="chat-header">
            <h2>Vibe Coding <span>Agent</span></h2>
            <div className="model-selector-wrap">
              {/* Change Review Button */}
              <button
                className={`icon-btn ${changePanelVisible ? 'active' : ''}`}
                title={`변경 검토${pendingChangeCount > 0 ? ` (${pendingChangeCount} pending)` : ''}`}
                style={{
                  fontSize: 14,
                  position: 'relative',
                  color: changePanelVisible ? 'var(--accent-color)' : undefined,
                  background: changePanelVisible ? 'rgba(124,106,239,0.12)' : undefined,
                }}
                onClick={() => setChangePanelVisible(!changePanelVisible)}
              >
                📋
                {pendingChangeCount > 0 && (
                  <span className="change-dot">{pendingChangeCount > 9 ? '9+' : pendingChangeCount}</span>
                )}
              </button>
              <button className="icon-btn" title="New Chat" style={{ fontSize: 14 }} onClick={createNewSession}>
                ➕
              </button>
              <button className="icon-btn" title="Chat History" style={{ fontSize: 14 }} onClick={() => setChatHistoryVisible(true)}>
                📜
              </button>
              <ModelSelector />
            </div>
          </div>

          <div className="chat-history" ref={chatHistoryRef}>
            {messages.length === 0 ? (
              <EmptyState onExampleClick={handleExampleClick} />
            ) : (
              messages.map((msg, i) => (
                <ChatMessage key={msg.id || `${msg.role}-${i}`} message={msg} />
              ))
            )}
            {isStreaming && (
              <div className="message assistant">
                <div className="avatar">🤖</div>
                <div className="bubble glass-panel">
                  <span className="typing-indicator"><span /><span /><span /></span>
                </div>
              </div>
            )}
          </div>

          <ChatInput
            onSend={handleSend}
            onStop={handleStop}
            isStreaming={isStreaming}
            textareaRef={registerInput}
          />

          <PlanToggleBar />
        </div>
      </div>
      </SplitPane>

      <ChatHistory visible={chatHistoryVisible} onClose={() => setChatHistoryVisible(false)} />
    </div>
  );
};

export default ChatPage;
