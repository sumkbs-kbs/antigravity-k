export const ChatPage = {
  render: () => `
    <div class="ide-layout">
      <!-- 모바일 전용 Top App Bar (CSS로 모바일에서만 노출됨) -->
      <div class="mobile-app-bar" style="display:none;">
        <button class="mobile-hamburger" id="mobile-hamburger-btn">☰</button>
        <span class="mobile-app-title">Antigravity-K</span>
        <div class="mobile-actions">
          <button id="mobile-command-palette-btn" class="icon-btn" title="Command Palette" style="font-size:18px;">🔎</button>
          <button id="mobile-agent-mgr-btn" class="icon-btn" title="Agent Manager" style="font-size:18px;">🤖</button>
          <button id="mobile-new-chat-btn" class="icon-btn" title="New Chat" style="font-size:18px;">➕</button>
        </div>
      </div>

      <!-- 왼쪽: 파일 탐색기 -->
      <div class="explorer-overlay" id="explorer-overlay"></div>
      <div class="ide-explorer glass-panel" id="ide-explorer">
        <div class="explorer-header" style="display:flex; justify-content:space-between; align-items:center;">
          <span class="explorer-title">EXPLORER</span>
          <div>
            <button id="new-folder-btn" class="icon-btn" title="New Folder">📁+</button>
            <button id="index-workspace-btn" class="icon-btn" title="폴더 지식 학습 (Index Workspace)">🧠</button>
            <button id="open-folder-btn" class="icon-btn" title="Open Folder">📁</button>
            <button id="refresh-tree-btn" class="icon-btn" title="Refresh">🔄</button>
          </div>
        </div>
        <div id="file-tree" class="file-tree">
          <div class="tree-loading">Loading workspace...</div>
        </div>
      </div>

      <!-- 폴더 선택 모달 -->
      <div id="folder-modal" class="modal-overlay" style="display:none;">
        <div class="modal-content glass-panel" style="width: 500px; max-height: 80vh; display: flex; flex-direction: column;">
          <div class="modal-header" style="padding: 16px; border-bottom: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin:0; font-size: 16px;">Open Folder</h3>
            <button id="close-modal-btn" class="icon-btn" style="color:var(--text-secondary);">✕</button>
          </div>
          <div style="padding: 8px 16px; background: rgba(0,0,0,0.2); font-size: 12px; color: var(--text-secondary); word-break: break-all;" id="current-browse-path">/</div>
          <div id="browse-list" style="flex:1; overflow-y:auto; padding: 8px 0;"></div>
          <div class="modal-footer" style="padding: 16px; border-top: 1px solid var(--glass-border); display: flex; justify-content: flex-end; gap: 8px;">
            <button id="cancel-folder-btn" class="btn" style="background: transparent; border: 1px solid var(--glass-border);">Cancel</button>
            <button id="select-folder-btn" class="btn" style="background: var(--accent-color);">Select This Folder</button>
          </div>
        </div>
      </div>

      <!-- 채팅 기록 모달 -->
      <div id="chat-history-modal" class="modal-overlay" style="display:none;">
        <div class="modal-content glass-panel" style="width: 400px; max-height: 80vh; display: flex; flex-direction: column;">
          <div class="modal-header" style="padding: 16px; border-bottom: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin:0; font-size: 16px;">Chat History</h3>
            <button id="close-history-modal-btn" class="icon-btn" style="color:var(--text-secondary);">✕</button>
          </div>
          <div id="chat-history-list" style="flex:1; overflow-y:auto; padding: 0;"></div>
        </div>
      </div>

      <!-- 새 폴더 생성 모달 -->
      <div id="new-folder-modal" class="modal-overlay" style="display:none; z-index: 9999;">
        <div class="modal-content glass-panel" style="width: 400px; display: flex; flex-direction: column;">
          <div class="modal-header" style="padding: 16px; border-bottom: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin:0; font-size: 16px;">New Folder</h3>
            <button id="close-new-folder-btn" class="icon-btn" style="color:var(--text-secondary);">✕</button>
          </div>
          <div style="padding: 16px;">
            <label style="display:block; margin-bottom:8px; font-size: 13px; color: var(--text-secondary);">새로 생성할 폴더 이름을 입력하세요 (워크스페이스 기준):</label>
            <input type="text" id="new-folder-input" style="width: 100%; padding: 8px; background: rgba(0,0,0,0.2); border: 1px solid var(--glass-border); color: #fff; border-radius: 4px;" placeholder="새 폴더">
          </div>
          <div class="modal-footer" style="padding: 16px; border-top: 1px solid var(--glass-border); display: flex; justify-content: flex-end; gap: 8px;">
            <button id="cancel-new-folder-btn" class="btn" style="background: transparent; border: 1px solid var(--glass-border);">Cancel</button>
            <button id="confirm-new-folder-btn" class="btn" style="background: var(--accent-color);">Create</button>
          </div>
        </div>
      </div>

      <!-- 중앙: 코드 뷰어 -->
      <div class="ide-editor glass-panel" style="display: flex; flex-direction: column; overflow: hidden; background: #1e1e1e;">
        <div class="editor-tabs" style="display: flex; background: #252526; border-bottom: 1px solid #1e1e1e; overflow-x: auto;">
          <div class="editor-tab active" style="padding: 10px 16px; background: #1e1e1e; color: #fff; font-size: 13px; font-family: sans-serif; display: flex; align-items: center; border-top: 1px solid #007acc; cursor: pointer;">
            <svg style="width:14px;height:14px;margin-right:6px;" viewBox="0 0 16 16" fill="#519aba"><path d="M13.71 4.29l-3-3L10 1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1V5l-.29-.71zM10 2.41L12.59 5H10V2.41zM13 14H4V2h5v4h4v8z"/></svg>
            <span id="editor-title">Welcome</span>
          </div>
        </div>
        <div class="editor-content" style="flex: 1; position: relative; padding: 0;">
          <!-- Monaco Editor가 마운트될 컨테이너 -->
          <div id="monaco-editor-container" style="position: absolute; top: 0; bottom: 0; left: 0; right: 0;"></div>
          <!-- 초기 메시지 (Monaco 로딩 전/파일 선택 전) -->
          <div id="editor-placeholder" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #666; font-size: 14px; pointer-events: none;">
            Select a file from the explorer to view its contents.
          </div>
        </div>
      </div>

      <!-- 프리뷰 창 (Artifact Preview) -->
      <div id="ide-preview-panel" class="ide-preview glass-panel" style="display: none; flex-direction: column; overflow: hidden; background: #ffffff;">
        <div class="editor-tabs" style="display: flex; background: #f0f0f0; border-bottom: 1px solid #ccc; justify-content: space-between; align-items: center; padding-right: 8px;">
          <div class="editor-tab active" style="padding: 10px 16px; background: #fff; color: #333; font-size: 13px; font-weight: bold; display: flex; align-items: center; border-top: 1px solid #007acc;">
            <span id="preview-title">Artifact Preview</span>
          </div>
          <button id="close-preview-btn" class="icon-btn" style="color: #666;">✕</button>
        </div>
        <div style="flex: 1; position: relative;">
          <iframe id="preview-iframe" style="width: 100%; height: 100%; border: none; background: #fff;" sandbox="allow-scripts allow-forms allow-popups allow-same-origin"></iframe>
        </div>
      </div>

      <!-- 오른쪽: AI 채팅 -->
      <div class="ide-chat">
        <div class="chat-container">
          <div class="chat-header">
            <h2>Vibe Coding <span>Agent</span></h2>
            <div class="model-selector-wrap" style="display:flex; gap:8px; align-items:center;">
              <button id="new-chat-btn" class="icon-btn" title="New Chat" style="font-size: 14px;">➕</button>
              <button id="history-btn" class="icon-btn" title="Chat History" style="font-size: 14px;">📜</button>
              <button id="open-agent-mgr-btn" class="icon-btn" title="Open Agent Manager" style="font-size: 14px;">🤖</button>
              <select id="model-select" class="glass-select">
                <option value="default">Default Local Model</option>
              </select>
            </div>
          </div>

          <div id="chat-history" class="chat-history">
            <div class="message system">
              <div class="avatar">✨</div>
              <div class="bubble glass-panel">
                Antigravity-K Vibe Coding 엔진에 오신 것을 환영합니다! 무엇을 개발할까요?
              </div>
            </div>
          </div>

          <div class="chat-input-wrapper" style="position: relative; display: flex; flex-direction: column; width: 100%;">
            <!-- Image preview container -->
            <div id="chat-image-preview-container" style="display: none; padding: 8px 12px; background: rgba(0,0,0,0.2); border-top-left-radius: 8px; border-top-right-radius: 8px; border-bottom: 1px solid rgba(255,255,255,0.1);">
              <div style="position: relative; display: inline-block;">
                <img id="chat-image-preview" src="" style="max-height: 60px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.2);">
                <button id="chat-image-clear-btn" style="position: absolute; top: -6px; right: -6px; background: #ff4444; color: white; border: none; border-radius: 50%; width: 18px; height: 18px; font-size: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center;">✕</button>
              </div>
            </div>

            <div class="chat-input-area glass-panel" style="display: flex; align-items: flex-end; gap: 8px; border-top-left-radius: 0; border-top-right-radius: 0;">
              <button id="chat-attach-btn" class="icon-btn" title="이미지 첨부 (Vision)" style="padding: 8px; font-size: 18px; opacity: 0.7; cursor: pointer; background: transparent; border: none; transition: opacity 0.2s;">📎</button>
              <input type="file" id="chat-file-input" accept="image/*" style="display: none;">
              <textarea id="chat-input" placeholder="명령어나 질문을 입력하세요... (이미지 Drag & Drop 가능)" rows="1" style="flex: 1; min-height: 40px; border: none; background: transparent; color: var(--text-primary); resize: none; padding: 8px 0; font-family: inherit;"></textarea>
              <button id="send-btn" class="glow-btn">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
              </button>
            </div>
          </div>

          <!-- Plan Toggle Bar -->
          <div class="plan-toggle-bar">
            <div class="plan-model-info">
              <span>⚡</span>
              <span id="plan-bar-model-name">Default Local Model</span>
            </div>
            <div class="plan-controls">
              <div id="auto-toggle" class="plan-toggle" title="Autonomous Mode: AI가 툴을 자율적으로 실행합니다">
                <span class="toggle-dot" style="background: var(--accent-color);"></span>
                <span>🤖 Auto</span>
              </div>
              <div id="plan-toggle" class="plan-toggle" title="Plan Mode: AI가 먼저 구현 계획을 수립합니다">
                <span class="toggle-dot"></span>
                <span>📋 Plan</span>
              </div>
              <div id="tdd-toggle" class="plan-toggle" title="TDD Mode: 다중 모델 경쟁 기반으로 테스트 주도 코딩을 수행합니다">
                <span class="toggle-dot" style="background: var(--success-color);"></span>
                <span>🧪 TDD Mode</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Agent Manager Overlay -->
    <div id="agent-manager-overlay" class="agent-manager-overlay"></div>

    <!-- Agent Manager Slide Panel -->
    <div id="agent-manager-panel" class="agent-manager-panel">
      <div class="agent-manager-header">
        <div>
          <span>🤖 Agent Manager</span>
          <div id="agent-manager-project" class="agent-manager-project">현재 프로젝트 기준</div>
        </div>
        <button id="close-agent-mgr-btn" class="close-agent-mgr" title="Close">✕</button>
      </div>
      <div id="agent-manager-body" class="agent-manager-body">
        <div class="agent-manager-empty">
          <span class="empty-icon">🤖</span>
          <span>실행 중인 에이전트가 없습니다</span>
        </div>
      </div>
    </div>
  `,

  init: () => {
    // ─── 1. 모델 목록 및 채팅 초기화 ───
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const history = document.getElementById('chat-history');
    const modelSelect = document.getElementById('model-select');
    const newChatBtn = document.getElementById('new-chat-btn');
    const historyBtn = document.getElementById('history-btn');
    const historyModal = document.getElementById('chat-history-modal');
    const closeHistoryModalBtn = document.getElementById('close-history-modal-btn');
    const chatHistoryList = document.getElementById('chat-history-list');

    // Vision / Attachment UI
    const attachBtn = document.getElementById('chat-attach-btn');
    const fileInput = document.getElementById('chat-file-input');
    const previewContainer = document.getElementById('chat-image-preview-container');
    const previewImg = document.getElementById('chat-image-preview');
    const clearImgBtn = document.getElementById('chat-image-clear-btn');

    // --- Modal Manager ---
    function hideAllModals() {
      if (historyModal) historyModal.style.display = 'none';
      const folderModal = document.getElementById('folder-modal');
      if (folderModal) folderModal.style.display = 'none';
      const newFolderModal = document.getElementById('new-folder-modal');
      if (newFolderModal) newFolderModal.style.display = 'none';
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        hideAllModals();
      }
      // Cmd+Backspace or Ctrl+Backspace to clear chat
      if ((e.metaKey || e.ctrlKey) && e.key === 'Backspace') {
        if (newChatBtn) newChatBtn.click();
      }
    });

    // --- Input Auto-resize ---
    input.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = (this.scrollHeight) + 'px';
      if (this.scrollHeight > 200) {
        this.style.overflowY = 'auto';
        this.style.height = '200px';
      } else {
        this.style.overflowY = 'hidden';
      }
    });
    // ----------------------

    let currentAttachedFile = null;

    // Handle File Selection
    const handleFile = (file) => {
      if (!file || !file.type.startsWith('image/')) return;
      currentAttachedFile = file;
      const reader = new FileReader();
      reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewContainer.style.display = 'block';
        // Adjust input area corners
        document.querySelector('.chat-input-area').style.borderTopLeftRadius = '0';
        document.querySelector('.chat-input-area').style.borderTopRightRadius = '0';
      };
      reader.readAsDataURL(file);
    };

    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) handleFile(e.target.files[0]);
    });
    clearImgBtn.addEventListener('click', () => {
      currentAttachedFile = null;
      fileInput.value = '';
      previewContainer.style.display = 'none';
      document.querySelector('.chat-input-area').style.borderTopLeftRadius = '';
      document.querySelector('.chat-input-area').style.borderTopRightRadius = '';
    });

    // Drag & Drop on chat input area
    const chatInputWrapper = document.querySelector('.chat-input-wrapper');
    chatInputWrapper.addEventListener('dragover', (e) => {
      e.preventDefault();
      chatInputWrapper.style.boxShadow = '0 0 0 2px var(--accent-color)';
    });
    chatInputWrapper.addEventListener('dragleave', () => {
      chatInputWrapper.style.boxShadow = '';
    });
    chatInputWrapper.addEventListener('drop', (e) => {
      e.preventDefault();
      chatInputWrapper.style.boxShadow = '';
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFile(e.dataTransfer.files[0]);
      }
    });

    // Preview Pane
    const previewPanel = document.getElementById('ide-preview-panel');
    const closePreviewBtn = document.getElementById('close-preview-btn');
    const previewIframe = document.getElementById('preview-iframe');
    const previewTitle = document.getElementById('preview-title');
    const ideEditor = document.querySelector('.ide-editor');

    closePreviewBtn.addEventListener('click', () => {
      previewPanel.style.display = 'none';
      ideEditor.style.display = 'flex'; // Restore editor
    });

    // global 렌더 함수 (onclick 등에서 호출)
    window.previewArtifact = function(filePath, fileName) {
      previewPanel.style.display = 'flex';
      // 에디터를 좁히거나 숨김 (간단히 숨기거나 flex 비율 조정)
      ideEditor.style.display = 'none';
      previewTitle.textContent = "Preview: " + fileName;

      // /api/read endpoint를 통해 파일 내용을 가져와서 iframe srcdoc에 주입
      fetch('/api/read?path=' + encodeURIComponent(filePath))
        .then(res => res.json())
        .then(data => {
          if (data.content) {
            previewIframe.srcdoc = data.content;
          } else {
            previewIframe.srcdoc = "<h3>Error loading preview</h3><p>" + (data.error || "Unknown error") + "</p>";
          }
        })
        .catch(err => {
          previewIframe.srcdoc = "<h3>Error fetching preview</h3><p>" + err.message + "</p>";
        });
    };

    let chatSessions = [];
    let activeSessionId = null;
    let chatMessages = [];
    let currentWorkspacePath = '/';

    function generateSessionId() {
      return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    function createNewSession() {
      activeSessionId = generateSessionId();
      chatMessages = [];
      saveChatHistory();
      renderChatMessages();
    }

    async function loadChatHistory() {
      // 1. localStorage 다중 세션 우선 로드 (세션별 대화 보존)
      const saved = localStorage.getItem('antigravity_chat_' + currentWorkspacePath);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            // 구버전 마이그레이션 (단일 배열 → 다중 세션)
            activeSessionId = generateSessionId();
            chatMessages = parsed;
            chatSessions = [{
              id: activeSessionId,
              title: chatMessages.length > 0 ? (chatMessages[0].content.substring(0, 15) + '...') : "Migrated Chat",
              updatedAt: new Date().toISOString(),
              messages: chatMessages
            }];
            saveChatHistory();
          } else if (parsed.sessions && parsed.sessions.length > 0) {
            // 다중 세션 복원
            chatSessions = parsed.sessions;
            activeSessionId = parsed.activeSessionId || chatSessions[0].id;
            const session = chatSessions.find(s => s.id === activeSessionId);
            chatMessages = session ? session.messages : [];
          } else {
            // 백엔드에서 초기 로드 (최초 1회만)
            await loadFromBackend();
          }
        } catch(e) {
          console.error("Failed to parse chat history:", e);
          chatSessions = [];
          createNewSession();
        }
      } else {
        // localStorage가 비어있으면 백엔드에서 로드
        await loadFromBackend();
      }

      if (!activeSessionId || chatSessions.length === 0) {
        createNewSession();
      } else {
        renderChatMessages();
      }
    }

    // 백엔드에서 세션 로드 (최초 1회 또는 localStorage 비어있을 때)
    async function loadFromBackend() {
      try {
        const res = await fetch('/api/session/messages');
        const data = await res.json();
        if (data.ok && data.messages && data.messages.length > 0) {
          activeSessionId = generateSessionId();
          chatMessages = data.messages;
          chatSessions = [{
            id: activeSessionId,
            title: chatMessages[0].content.substring(0, 20) + (chatMessages[0].content.length > 20 ? '...' : ''),
            updatedAt: new Date().toISOString(),
            messages: chatMessages
          }];
          saveChatHistory();
        } else {
          chatSessions = [];
        }
      } catch (e) {
        console.error("Failed to fetch backend session:", e);
        chatSessions = [];
      }
    }

    function renderChatMessages() {
      history.innerHTML = '';
      if (chatMessages.length === 0) {
        // P1-1: 빈 상태 시작 화면 — 예시 질문 칩 + 온보딩
        renderEmptyState();
      } else {
        chatMessages.forEach(msg => {
          appendMessage(msg.role, msg.role === 'assistant' ? formatContent(msg.content) : msg.content, true);
        });
      }
      history.scrollTop = history.scrollHeight;
      setTimeout(() => {
        if (window.mermaid) {
           try { window.mermaid.init(undefined, document.querySelectorAll('.mermaid')); } catch(e){}
        }
      }, 100);
    }

    // P1-1: 빈 상태 시작 화면 렌더링
    function renderEmptyState() {
      const emptyDiv = document.createElement('div');
      emptyDiv.className = 'empty-state-container';
      emptyDiv.innerHTML = `
        <div class="empty-state-logo">🚀</div>
        <div class="empty-state-title">Antigravity-K에 오신 것을 환영합니다</div>
        <div class="empty-state-subtitle">
          로컬 AI 엔지니어링 에이전트입니다. 코드 작성, 파일 편집, 웹 검색,
          날씨/주가 조회 등 다양한 작업을 도와드릴 수 있습니다.
        </div>
        <div class="empty-state-chips">
          <button class="example-chip" onclick="document.getElementById('chat-input').value='파일 목록 보여줘'; document.getElementById('chat-input').focus();">📁 파일 목록 보여줘</button>
          <button class="example-chip" onclick="document.getElementById('chat-input').value='오늘 서울 날씨 알려줘'; document.getElementById('chat-input').focus();">🌤️ 오늘 날씨 알려줘</button>
          <button class="example-chip" onclick="document.getElementById('chat-input').value='니가 할 수 있는 게 뭐야?'; document.getElementById('chat-input').focus();">🤖 무엇을 할 수 있어?</button>
          <button class="example-chip" onclick="document.getElementById('chat-input').value='이 프로젝트 코드 리뷰해줘'; document.getElementById('chat-input').focus();">🔍 코드 리뷰해줘</button>
        </div>
      `;
      history.appendChild(emptyDiv);
    }

    function saveChatHistory() {
      let session = chatSessions.find(s => s.id === activeSessionId);
      if (!session) {
        session = {
          id: activeSessionId,
          title: "New Chat",
          updatedAt: new Date().toISOString(),
          messages: chatMessages
        };
        chatSessions.unshift(session);
      } else {
        // 첫 유저 메시지 시 title 업데이트
        if (session.title === "New Chat" && chatMessages.length > 0) {
           const firstUserMsg = chatMessages.find(m => m.role === 'user');
           if (firstUserMsg) {
             session.title = firstUserMsg.content.substring(0, 20) + (firstUserMsg.content.length > 20 ? '...' : '');
           }
        }
        session.messages = chatMessages;
        session.updatedAt = new Date().toISOString();
        // 배열의 맨 앞으로 이동 (최신)
        chatSessions = [session, ...chatSessions.filter(s => s.id !== activeSessionId)];
      }

      const payload = {
        activeSessionId,
        sessions: chatSessions
      };
      localStorage.setItem('antigravity_chat_' + currentWorkspacePath, JSON.stringify(payload));
    }

    function renderHistoryModal() {
      chatHistoryList.innerHTML = '';
      if (chatSessions.length === 0) {
        chatHistoryList.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-secondary);">No chat history found.</div>';
        return;
      }

      chatSessions.forEach(session => {
        const div = document.createElement('div');
        div.className = 'history-item' + (session.id === activeSessionId ? ' active' : '');
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.padding = '10px 12px';
        div.style.borderRadius = '8px';
        div.style.cursor = 'pointer';
        div.style.transition = 'background 0.15s ease';
        div.style.position = 'relative';

        const dateStr = new Date(session.updatedAt).toLocaleString();

        div.innerHTML = `
          <div style="flex:1; min-width:0; overflow:hidden;">
            <div class="history-title" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:13px; font-weight:500;">${escapeHTML(session.title)}</div>
            <div class="history-date" style="font-size:11px; color:var(--text-muted,#565f89); margin-top:2px;">${dateStr}</div>
          </div>
          <button class="delete-session-btn" title="삭제" style="
            flex-shrink:0;
            margin-left:auto;
            background:transparent; border:none; color:#565f89;
            font-size:16px; padding:4px 8px; cursor:pointer;
            opacity:0; transition:opacity 0.2s ease, color 0.2s ease;
            border-radius:6px;
            align-self:center;
          ">🗑️</button>
        `;

        // hover 시 삭제 버튼 표시
        div.addEventListener('mouseenter', () => {
          div.style.background = 'rgba(255,255,255,0.04)';
          div.querySelector('.delete-session-btn').style.opacity = '1';
        });
        div.addEventListener('mouseleave', () => {
          div.style.background = '';
          div.querySelector('.delete-session-btn').style.opacity = '0';
        });

        // 전체 행 클릭 시 (히스토리 로드)
        div.addEventListener('click', (e) => {
          // 삭제 버튼 클릭 이벤트가 전달되지 않도록 방어 로직 추가
          if (e.target.closest('.delete-session-btn')) return;

          activeSessionId = session.id;
          chatMessages = session.messages;
          saveChatHistory();
          renderChatMessages();
          historyModal.style.display = 'none';
        });

        // 삭제 버튼 클릭 시 이벤트
        const deleteBtn = div.querySelector('.delete-session-btn');
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (confirm('정말 이 대화 기록을 삭제하시겠습니까?')) {
            // chatSessions 배열에서 제거
            chatSessions = chatSessions.filter(s => s.id !== session.id);

            // 삭제한 세션이 현재 열려있는 세션인 경우
            if (activeSessionId === session.id) {
              createNewSession();
            } else {
              saveChatHistory();
            }

            // 모달 리렌더링
            renderHistoryModal();
          }
        });

        chatHistoryList.appendChild(div);
      });
    }

    if (newChatBtn) {
      newChatBtn.addEventListener('click', createNewSession);
    }

    if (historyBtn) {
      historyBtn.addEventListener('click', () => {
        hideAllModals();
        renderHistoryModal();
        historyModal.style.display = 'flex';
      });
    }

    if (closeHistoryModalBtn) {
      closeHistoryModalBtn.addEventListener('click', () => {
        historyModal.style.display = 'none';
      });
    }

    // ─── 1.5. Event Bus WebSocket 연동 (Real-time Observability) ───
    let eventWs = null;
    let activeToolContainer = null;

    function connectEventStream() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // Fallback to localhost:8000 if not served by FastAPI
      const host = window.location.port === "5173" || window.location.port === "3000" ? "localhost:8000" : window.location.host;
      const wsUrl = `${protocol}//${host}/v1/ws/events`;

      eventWs = new WebSocket(wsUrl);

      eventWs.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          handleAgentEvent(payload.event, payload.data);
        } catch(err) {
          console.error("WS Parse error", err);
        }
      };

      eventWs.onclose = () => {
        setTimeout(connectEventStream, 3000); // Auto-reconnect
      };
    }

    function handleAgentEvent(event, data) {
      if (!history) return;
      const lastMessage = history.lastElementChild;
      if (!lastMessage || !lastMessage.classList.contains('assistant')) return;

      const bubble = lastMessage.querySelector('.bubble');
      if (!bubble) return;

      if (event === "ToolExecutionStarted") {
        const toolName = data.name || data.tool_name || "unknown_tool";
        // Remove existing active container if any
        if (activeToolContainer && activeToolContainer.parentNode) {
          activeToolContainer.remove();
        }
        activeToolContainer = document.createElement('div');
        activeToolContainer.className = 'tool-timeline-badge start';
        activeToolContainer.style.marginTop = '8px';
        activeToolContainer.innerHTML = `<span class="icon">⚙️</span> <span class="text">Running Tool <b style="color:var(--accent-color);">${toolName}</b>... <span class="typing-indicator" style="height:12px;margin-left:4px;"><span></span><span></span><span></span></span></span>`;
        bubble.appendChild(activeToolContainer);
        history.scrollTop = history.scrollHeight;
      }
      else if (event === "ToolExecutionFinished") {
        if (activeToolContainer && activeToolContainer.parentNode) {
          activeToolContainer.remove();
          activeToolContainer = null;
        }
      }
      else if (event === "FailureDetected") {
        const errDiv = document.createElement('div');
        errDiv.className = 'tool-timeline-badge error';
        errDiv.style.marginTop = '8px';
        errDiv.innerHTML = `<span class="icon">⚠️</span> <span class="text"><b>Failure Detected:</b> Agent is attempting to recover...</span>`;
        bubble.appendChild(errDiv);
        history.scrollTop = history.scrollHeight;
        if (activeToolContainer && activeToolContainer.parentNode) activeToolContainer.remove();
      }
      else if (event === "CognitiveAdaptation") {
        const adaptDiv = document.createElement('div');
        adaptDiv.style.marginTop = '8px';
        adaptDiv.innerHTML = `<span class="agent-badge adapting">ADAPTING</span> <span style="font-size: 13px; color: var(--warning);">동적 전략 수정 중...</span>`;
        bubble.appendChild(adaptDiv);
        history.scrollTop = history.scrollHeight;
      }
      else if (event === "PlanningModeStarted") {
        const planDiv = document.createElement('div');
        planDiv.style.marginTop = '8px';
        planDiv.innerHTML = `<span class="agent-badge planning">PLANNING</span> <span style="font-size: 13px; color: var(--accent-color);">실행 계획 수립 중...</span>`;
        bubble.appendChild(planDiv);
        history.scrollTop = history.scrollHeight;
      }
      else if (event === "FileOpened" || event === "FileModified") {
        if (typeof monacoLoaded !== 'undefined' && monacoLoaded && monacoEditor) {
          const fileName = data.filepath ? data.filepath.split(/[/\\]/).pop() : "unknown";
          const lang = typeof getLanguageFromExt === 'function' ? getLanguageFromExt(fileName) : 'plaintext';
          const titleEl = document.getElementById('editor-title');
          if (titleEl) titleEl.textContent = fileName;
          const ph = document.getElementById('editor-placeholder');
          if (ph) ph.style.display = 'none';
          monaco.editor.setModelLanguage(monacoEditor.getModel(), lang);
          monacoEditor.setValue(data.content || "");

          // Show preview panel automatically if HTML or React component is modified (optional UX enhancement)
          if (data.filepath && (data.filepath.endsWith('.html'))) {
            // Uncomment if auto-preview is desired
            // window.previewArtifact(data.filepath, fileName);
          }
        }
      }
    }

    connectEventStream();

    // ─── 모델 목록 + 기본 모델 로드 ───
    function loadModels() {
      Promise.all([
        fetch('/v1/models').then(r => r.json()),
        fetch('/api/settings', { skipPinModal: true }).then(r => r.json()).catch(() => ({ settings: {} }))
      ]).then(([modelsData, settingsData]) => {
        if (!modelsData || !modelsData.data || modelsData.data.length === 0) return;

        const defaults = settingsData.settings?.defaults || {};
        const models = modelsData.data;

        // 역할별 그룹핑
        const roleOrder = ['reasoning', 'coding', 'vision', 'embedding'];
        const roleLabels = { reasoning: '🧠 Reasoning', coding: '💻 Coding', vision: '👁️ Vision', embedding: '📐 Embedding' };
        const grouped = {};
        models.forEach(m => {
          const role = m.role || 'other';
          if (!grouped[role]) grouped[role] = [];
          grouped[role].push(m);
        });

        modelSelect.innerHTML = '';

        roleOrder.forEach(role => {
          const list = grouped[role];
          if (!list || list.length === 0) return;

          const optgroup = document.createElement('optgroup');
          optgroup.label = roleLabels[role] || role;

          list.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            const isDefault = defaults[role] === model.id;
            option.textContent = isDefault ? `⭐ ${model.id}` : model.id;
            option.title = model.description || model.id;
            if (isDefault) option.dataset.default = 'true';
            optgroup.appendChild(option);
          });
          modelSelect.appendChild(optgroup);
        });

        // 기본 모델 자동 선택
        const defaultModel = defaults.reasoning || (models[0] && models[0].id);
        if (defaultModel) {
          for (const option of modelSelect.options) {
            if (option.value === defaultModel || option.textContent.includes(defaultModel)) {
              option.selected = true;
              break;
            }
          }
        }

        // ⚙️ Set as Default 버튼 (모델 선택 옆)
        const wrap = modelSelect.closest('.model-selector-wrap');
        if (wrap && !document.getElementById('set-default-model-btn')) {
          const setBtn = document.createElement('button');
          setBtn.id = 'set-default-model-btn';
          setBtn.className = 'icon-btn';
          setBtn.title = '현재 선택한 모델을 기본값으로 설정';
          setBtn.innerHTML = '⭐';
          setBtn.style.fontSize = '14px';
          setBtn.style.opacity = '0.6';
          setBtn.style.transition = 'opacity 0.2s';
          setBtn.addEventListener('mouseenter', () => setBtn.style.opacity = '1');
          setBtn.addEventListener('mouseleave', () => setBtn.style.opacity = '0.6');
          setBtn.addEventListener('click', async () => {
            const selectedModel = modelSelect.value;
            if (!selectedModel || selectedModel === 'default') return;
            setBtn.disabled = true;
            setBtn.innerHTML = '⏳';
            try {
              const res = await fetch('/api/models/default', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: selectedModel })
              });
              const data = await res.json();
              if (data.ok) {
                window.showToast?.(`✅ 기본 모델 변경: ${selectedModel}`, 'success');
                loadModels(); // Reload to update stars
              } else {
                window.showToast?.(`❌ 설정 실패: ${data.detail || '오류'}`, 'error');
              }
            } catch (err) {
              window.showToast?.(`❌ 오류: ${err.message}`, 'error');
            } finally {
              setBtn.disabled = false;
              setBtn.innerHTML = '⭐';
            }
          });
          // Insert before new-chat-btn
          const refBtn = wrap.querySelector('#new-chat-btn');
          if (refBtn) {
            wrap.insertBefore(setBtn, refBtn);
          } else {
            wrap.appendChild(setBtn);
          }
        }
      }).catch(err => console.error("Failed to load models:", err));
    }

    loadModels();

    input.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = (this.scrollHeight) + 'px';
      if (this.value.trim() !== '') {
        sendBtn.classList.add('active');
      } else {
        sendBtn.classList.remove('active');
      }
    });

    let isComposing = false;
    input.addEventListener('compositionstart', () => { isComposing = true; });
    input.addEventListener('compositionend', () => { isComposing = false; });

    let currentAbortController = null;
    const sendIconHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
    const stopIconHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12"></rect></svg>';

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !isComposing && !e.isComposing) {
        e.preventDefault();
        if (!currentAbortController) {
          sendMessage();
        }
      }
    });

    sendBtn.addEventListener('click', () => {
      if (currentAbortController) {
        currentAbortController.abort();
      } else {
        sendMessage();
      }
    });

    async function sendMessage() {
      const text = input.value.trim();
      if (!text && !currentAttachedFile) return;

      // Build multimodal content if image is attached
      let userContent = text;
      let displayText = text;
      if (currentAttachedFile && previewImg.src) {
        const imageDataUrl = previewImg.src;
        userContent = [
          { type: "text", text: text || "이 이미지를 분석해주세요." },
          { type: "image_url", image_url: { url: imageDataUrl } }
        ];
        displayText = text + ' 📎🖼️';
        // Clear attachment after send
        currentAttachedFile = null;
        fileInput.value = '';
        previewContainer.style.display = 'none';
        document.querySelector('.chat-input-area').style.borderTopLeftRadius = '';
        document.querySelector('.chat-input-area').style.borderTopRightRadius = '';
      }

      appendMessage('user', displayText, false);
      chatMessages.push({role: "user", content: userContent});
      saveChatHistory();

      input.value = '';
      input.style.height = 'auto';
      sendBtn.classList.remove('active');

      const model = document.getElementById('model-select').value;
      const thinkingBadgeHTML = '<div style="display:inline-flex; align-items:center; gap:8px; font-size:13px; color:var(--text-secondary); padding:6px 12px; border-radius:8px; background:rgba(255,255,255,0.05); border:1px solid var(--glass-border);">🧠 Thinking <span class="typing-indicator" style="margin:0; height:12px;"><span></span><span></span><span></span></span></div>';
      const generatingBadgeHTML = '<span style="display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--accent-color); margin-left:8px; padding:2px 8px; border-radius:12px; background:rgba(0,122,204,0.1); border:1px solid rgba(0,122,204,0.3); font-weight:500;">✍️ Generating<span class="blinking-cursor" style="margin:0; height:12px; background-color:var(--accent-color);"></span></span>';

      const assistantMsgDiv = appendMessage('assistant', thinkingBadgeHTML, false);
      let assistantContent = '';
      let assistantMsgObj = null;

      currentAbortController = new AbortController();
      sendBtn.innerHTML = stopIconHTML;
      sendBtn.classList.add('active');
      sendBtn.style.color = '#ff4444'; // Stop btn color

      try {
        const payload = {
          model: model,
          messages: chatMessages,
          stream: true,
          agent_mode: true,
          plan_mode: !!document.getElementById('plan-toggle')?.classList.contains('active'),
          tdd_mode: !!document.getElementById('tdd-toggle')?.classList.contains('active')
        };

        let response;
        try {
          response = await fetch('/v1/chat/completions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
            signal: currentAbortController.signal
          });

          if (!response.ok && response.status >= 500) {
            throw new Error(`Server returned ${response.status}`);
          }
        } catch (fetchErr) {
          if (fetchErr.name === 'AbortError') throw fetchErr;
          console.warn('Streaming request failed or blocked. Falling back to non-streaming mode...', fetchErr);
          payload.stream = false;
          assistantMsgDiv.querySelector('.bubble').innerHTML = '<span style="color:var(--text-secondary); font-size:13px;">(사내망 스트리밍 차단 감지: 우회 모드로 안전하게 재요청 중... 잠시만 기다려주세요)</span>';

          response = await fetch('/v1/chat/completions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
            signal: currentAbortController.signal
          });
        }

        if (!response.ok) throw new Error('Network response was not ok: ' + response.status);

        // 빈 어시스턴트 메시지를 미리 저장하여, 새로고침 시에도 마지막 메시지가 assistant가 되게 보장
        assistantMsgObj = {role: "assistant", content: ""};
        chatMessages.push(assistantMsgObj);
        saveChatHistory();

        const contentSpan = assistantMsgDiv.querySelector('.bubble');

        if (!payload.stream) {
          const data = await response.json();
          assistantContent = data.choices && data.choices[0] && data.choices[0].message ? data.choices[0].message.content : '';
          assistantMsgObj.content = assistantContent;
          saveChatHistory();
          contentSpan.innerHTML = formatContent(assistantContent);
          if (ChatPage.refreshFileTree) ChatPage.refreshFileTree();
          renderDiffs(assistantMsgDiv);
          if (window.mermaid) {
             try { window.mermaid.init(undefined, document.querySelectorAll('.mermaid')); } catch(e){}
          }
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let buffer = '';
        let isFirstChunk = true;
        let lastSaveTime = Date.now();
        let _streamRenderPending = false; // P0-2: 디바운스 렌더링 플래그
        let _rafId = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            assistantMsgObj.content = assistantContent;
            saveChatHistory();

            // 스트리밍이 끝나면 커서를 제거하고 최종 렌더링
            contentSpan.innerHTML = formatContent(assistantContent);

            // 채팅 완료 시 파일 트리 자동 새로고침 및 디프 렌더링
            if (ChatPage.refreshFileTree) ChatPage.refreshFileTree();
            renderDiffs(assistantMsgDiv);
            if (window.mermaid) {
               try { window.mermaid.init(undefined, document.querySelectorAll('.mermaid')); } catch(e){}
            }
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          let eolIndex;

          while ((eolIndex = buffer.indexOf('\n')) >= 0) {
            const line = buffer.slice(0, eolIndex).trim();
            buffer = buffer.slice(eolIndex + 1);

            if (line.startsWith('data: ') && line !== 'data: [DONE]') {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.choices && data.choices[0].delta && data.choices[0].delta.content) {
                  if (isFirstChunk) {
                    contentSpan.innerHTML = '';
                    isFirstChunk = false;
                  }
                  const chunkText = data.choices[0].delta.content;
                  assistantContent += chunkText;

                  // Trigger toast for specific agent actions
                  if (chunkText.includes('File created:') || chunkText.includes('Created file') || chunkText.includes('Successfully wrote')) {
                    if (window.showToast) window.showToast('File Generated', 'success');
                  } else if (chunkText.includes('Directory created:') || chunkText.includes('Created folder')) {
                    if (window.showToast) window.showToast('Folder Generated', 'success');
                  }

                  // P0-2: 디바운스 렌더링 — 매 토큰마다가 아닌 requestAnimationFrame으로 제한
                  if (!_streamRenderPending) {
                    _streamRenderPending = true;
                    _rafId = requestAnimationFrame(() => {
                      contentSpan.innerHTML = formatContent(assistantContent) + generatingBadgeHTML;
                      history.scrollTop = history.scrollHeight;
                      _streamRenderPending = false;
                    });
                  }

                  // 주기적으로 로컬스토리지에 저장 (1초 간격)
                  if (Date.now() - lastSaveTime > 1000) {
                    assistantMsgObj.content = assistantContent;
                    saveChatHistory();
                    lastSaveTime = Date.now();
                  }
                }
              } catch (e) {}
            }
          }
        }
      } catch (err) {
        if (err.name === 'AbortError') {
          console.log('Generation stopped by user');
          if (assistantContent && assistantMsgObj) {
            assistantMsgObj.content = assistantContent + '\n\n*(중단됨)*';
            saveChatHistory();
            assistantMsgDiv.querySelector('.bubble').innerHTML = formatContent(assistantContent) + '<br><span style="color:var(--text-muted); font-size:12px;">*(중단됨)*</span>';
          } else {
            if (assistantMsgObj) chatMessages.pop(); // Remove the empty message
            saveChatHistory();
            assistantMsgDiv.remove();
          }
        } else {
          console.error(err);
          assistantMsgDiv.querySelector('.bubble').innerHTML = '<span class="error-text">API 요청 중 오류가 발생했습니다: ' + err.message + '</span>';
        }
      } finally {
        currentAbortController = null;
        sendBtn.innerHTML = sendIconHTML;
        sendBtn.style.color = '';
        if (input.value.trim() === '') {
          sendBtn.classList.remove('active');
        }

        // P0-2: 디바운스 rAF 취소 + pending 리셋 (지연 콜백이 배지를 다시 붙이지 않도록)
        if (_rafId) cancelAnimationFrame(_rafId);
        _streamRenderPending = false;

        // 스트리밍 완료 후 Generating 배지/커서 제거 및 최종 렌더링
        if (assistantMsgDiv) {
          const contentSpan = assistantMsgDiv.querySelector('.bubble');
          if (contentSpan) {
            // generatingBadgeHTML, blinking-cursor, generating-badge 모두 제거
            contentSpan.innerHTML = formatContent(assistantContent);
          }
          highlightCodeBlocks(assistantMsgDiv);
          addMessageActions(assistantMsgDiv, assistantContent);
        }
      }
    }

    function appendMessage(role, content) {
      const msgDiv = document.createElement('div');
      msgDiv.className = 'message ' + role;
      const avatar = role === 'user' ? '👤' : '🤖';
      msgDiv.innerHTML = '<div class="avatar">' + avatar + '</div>' +
        '<div class="bubble glass-panel">' + (role === 'user' ? escapeHTML(content) : content) + '</div>';
      history.appendChild(msgDiv);
      history.scrollTop = history.scrollHeight;
      setTimeout(() => msgDiv.classList.add('visible'), 10);
      // P0-1: 코드 블록 문법 강조 적용
      if (role === 'assistant') {
        highlightCodeBlocks(msgDiv);
        addMessageActions(msgDiv, content);
      }
      return msgDiv;
    }

    // P0-1: 코드 블록에 highlight.js 적용
    function highlightCodeBlocks(container) {
      if (!window.hljs) return;
      container.querySelectorAll('pre.code-block').forEach(pre => {
        // 이미 처리된 블록은 스킵
        if (pre.dataset.highlighted) return;
        // code 요소로 감싸서 highlight.js 적용
        const code = pre.querySelector('code') || pre;
        const text = code.textContent;
        // 언어 추출 (header에서)
        const header = pre.previousElementSibling;
        const lang = header && header.className.includes('code-block-header')
          ? header.textContent.trim().split(/\s+/)[0].toLowerCase()
          : '';
        try {
          if (lang && window.hljs.getLanguage(lang)) {
            code.innerHTML = window.hljs.highlight(text, { language: lang }).value;
          } else {
            code.innerHTML = window.hljs.highlightAuto(text).value;
          }
          pre.dataset.highlighted = 'true';
        } catch (e) { /* highlight 실패 시 무시 */ }
      });
    }

    // P0-3: 메시지 액션 버튼 (복사, 재생성)
    function addMessageActions(msgDiv, rawContent) {
      const bubble = msgDiv.querySelector('.bubble');
      if (!bubble) return;
      const actionBar = document.createElement('div');
      actionBar.className = 'message-actions';
      actionBar.innerHTML = `
        <button class="msg-action-btn" title="복사" onclick="
          navigator.clipboard.writeText(this.closest('.message').querySelector('.bubble').innerText)
            .then(() => { this.textContent='✓ 복사됨'; setTimeout(() => this.textContent='📋 복사', 1500); })
        ">📋 복사</button>
      `;
      bubble.appendChild(actionBar);
    }

    function escapeHTML(str) {
      return str.replace(/[&<>'"]/g,
        tag => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[tag])
      ).replace(/\n/g, '<br>');
    }

    function formatContent(str) {
      // ── 1단계: HTML 이스케이프 (raw text 보호) ──
      let text = str;
      const escapeMarkdownHTML = (value) => String(value).replace(/[&<>'"]/g,
        tag => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[tag])
      );
      const safeCarouselImageSrc = (value) => {
        const src = String(value || '').trim();
        if (/^(https?:\/\/|data:image\/|\/|\.\/|\.\.\/)/i.test(src)) return src;
        return '';
      };
      const safeMarkdownUrl = (value) => {
        const url = String(value || '').trim();
        if (/^(https?:\/\/|mailto:|\/|\.\/|\.\.\/|#)/i.test(url)) return escapeMarkdownHTML(url);
        return '#';
      };

      // ── 2단계: 코드블록 보호 (마크다운 처리 전에 추출) ──
      const codeBlocks = [];
      // 삼중 백틱 코드블록 추출
      text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push({ lang: lang || '', code: code });
        return `%%CODEBLOCK_${idx}%%`;
      });

      // 인라인 코드 보호
      const inlineCodes = [];
      text = text.replace(/`([^`]+)`/g, (match, code) => {
        const idx = inlineCodes.length;
        inlineCodes.push(code);
        return `%%INLINE_${idx}%%`;
      });

      // ── 2.5단계: 백엔드 HTML & <think> 태그 보호 ──
      text = text.replace(/<think>/g, '%%THINK_START%%');
      text = text.replace(/<\/think>/g, '%%THINK_END%%');

      // 오케스트레이터가 주입하는 HTML 보호
      const htmlBlocks = [];
      text = text.replace(/<details[^>]*>|<\/details>|<summary[^>]*>|<\/summary>|<div[^>]*>|<\/div>|<section[^>]*>|<\/section>/g, (match) => {
        const idx = htmlBlocks.length;
        htmlBlocks.push(match);
        return `%%HTML_${idx}%%`;
      });

      // ── 3단계: HTML 이스케이프 ──
      text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

      // 보호한 HTML 복원
      text = text.replace(/%%HTML_(\d+)%%/g, (match, idx) => {
        return htmlBlocks[parseInt(idx)];
      });

      // ── 4단계: 에이전트 배지 (마크다운 변환 전에 처리) ──
      const agentBadges = {
        'CEO': ['ceo', '🏢'], 'WORKER': ['worker', '👨‍💻'],
        'ENG_MANAGER': ['eng', '🏗️'], 'QA': ['qa', '🔍'],
        'DESIGNER': ['designer', '🎨'], 'ARCHITECT': ['architect', '🏗️'],
        'PROPOSER': ['proposer', '💡'], 'CRITIC': ['critic', '⚖️'],
        'ARBITER': ['arbiter', '🔨'], 'SELF': ['self', '💬']
      };
      for (const [name, [cls, emoji]] of Object.entries(agentBadges)) {
        const re = new RegExp(`\\*\\*\\[?${name}\\]?\\*\\*`, 'g');
        text = text.replace(re, `<span class="agent-badge ${cls}">${emoji} ${name}</span>`);
      }

      // ── 4.5단계: 에이전트 타임라인 / 도구 시각화 (P1-9) ──
      // **도구 실행** (step X/Y): %%INLINE_Z%%
      text = text.replace(/\*\*도구 실행\*\*\s*\(step\s*(\d+)\/(\d+)\):\s*(%%INLINE_\d+%%)/g,
        '<div class="tool-timeline-badge start"><span class="icon">🛠️</span> <span class="text">Executing Tool <b>$3</b> <span class="step-info">(Step $1/$2)</span></span></div>'
      );
      // 🐍 **[Ouroboros Guard]** ...
      text = text.replace(/🐍 \*\*\[Ouroboros Guard\]\*\*(.*)/g,
        '<div class="tool-timeline-badge warning"><span class="icon">🐍</span> <span class="text"><b>Ouroboros Guard:</b>$1</span></div>'
      );
      // ⚠️ **[Step Limit]** ...
      text = text.replace(/⚠️ \*\*\[Step Limit\]\*\*(.*)/g,
        '<div class="tool-timeline-badge error"><span class="icon">🛑</span> <span class="text"><b>Step Limit:</b>$1</span></div>'
      );
      // ⚠️ **[TOOL CALL PARSE ERROR]** ...
      text = text.replace(/⚠️ \*\*\[TOOL CALL PARSE ERROR\](.*)\*\*/g,
        '<div class="tool-timeline-badge error"><span class="icon">⚠️</span> <span class="text"><b>Parse Error:</b>$1</span></div>'
      );
      // 📊 **[Token Usage]** ...
      text = text.replace(/📊 (?:Tokens Used|\*\*\[Token Usage\]\*\*):?\s*In:\s*(\d+)(?:\s*tokens)?\s*\|\s*Out:\s*(\d+)(?:\s*tokens)?/gi,
        '<div class="tool-timeline-badge token"><span class="icon">📊</span> <span class="text"><b>Tokens Used:</b> <span class="token-val">In: $1</span> | <span class="token-val">Out: $2</span></span></div>'
      );

      // 🔄 **[Quality Retry]** ...
      text = text.replace(/🔄 \*\*품질 미달 \(([\d]+)%\)\*\* — 자동 개선 중\.\.\./g,
        '<div class="tool-timeline-badge warning"><span class="icon">🔄</span> <span class="text"><b>Quality Retry:</b> Score $1% - Auto improving...</span></div>'
      );
      // ✋ [APPROVAL REQUIRED] ...
      text = text.replace(/\[APPROVAL REQUIRED\]\s*([^<]*)(<br>|\n)?[^\n]*Wait for their 'Yes' before retrying\./g, (match, msg) => {
        return `<div class="tool-timeline-badge approval-box" style="border: 2px solid var(--accent-color); background: rgba(0, 122, 204, 0.1); padding: 12px; margin-top: 8px; border-radius: 8px;">
          <div style="display:flex; align-items:center; margin-bottom: 8px;">
            <span class="icon" style="font-size:20px; margin-right:12px;">✋</span>
            <div style="display:flex; flex-direction:column;">
              <span class="text" style="font-weight:bold; color:var(--text-primary); font-size:14px;">APPROVAL REQUIRED</span>
              <span style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${msg.trim()}</span>
            </div>
          </div>
          <div style="display:flex; gap:8px; margin-top:12px;">
            <button class="glow-btn" onclick="document.getElementById('chat-input').value='승인합니다'; document.getElementById('send-btn').click();" style="flex:1; background:var(--accent-color); border:none; border-radius:4px; padding:8px; color:#fff; cursor:pointer;">승인 (Approve)</button>
            <button class="btn" onclick="document.getElementById('chat-input').value='거절합니다'; document.getElementById('send-btn').click();" style="flex:1; background:transparent; border:1px solid var(--glass-border); border-radius:4px; padding:8px; color:var(--text-primary); cursor:pointer;">거절 (Reject)</button>
          </div>
        </div>`;
      });
      // 🎨 **[ARTIFACT GENERATED]** ...
      // format: [ARTIFACT GENERATED: filename.html (Type: html)]\nSuccessfully saved to /path/to/file
      text = text.replace(/\[ARTIFACT GENERATED: (.*?) \(Type: (.*?)\)\]\nSuccessfully saved to (.*?)\.?/g, (match, fname, type, path) => {
        let btnHtml = '';
        if (type === 'html' || type === 'react') {
          btnHtml = `<button class="btn preview-btn" onclick="window.previewArtifact('${path.replace(/\\/g, '\\\\')}', '${fname}')" style="margin-left:auto; background:var(--accent-color); font-size:11px; padding: 4px 8px;">View Preview</button>`;
        }
        return `<div class="tool-timeline-badge artifact" style="border-left: 3px solid #10b981; background: rgba(16, 185, 129, 0.1); width:100%; display:flex; align-items:center;">
                  <span class="icon" style="margin-right:8px;">🎨</span>
                  <div style="display:flex; flex-direction:column;">
                    <span class="text" style="font-weight:bold;">Artifact: ${fname}</span>
                    <span style="font-size:11px; color:#aaa;">Saved to project</span>
                  </div>
                  ${btnHtml}
                </div>`;
      });

      // ── 5단계: 블록 요소 (줄 단위 처리) ──
      const lines = text.split('\n');
      const result = [];
      let inList = false;
      let listType = '';
      let inTable = false;
      let tableRows = [];
      let inBlockquote = false;
      let blockquoteLines = [];

      function closeList() {
        if (inList) {
          result.push(listType === 'ul' ? '</ul>' : '</ol>');
          inList = false;
        }
      }
      function closeTable() {
        if (inTable && tableRows.length > 0) {
          let html = '<div class="md-table-wrap"><table class="md-table">';
          tableRows.forEach((row, idx) => {
            const tag = idx === 0 ? 'th' : 'td';
            const rowClass = idx === 0 ? ' class="md-table-header"' : '';
            html += `<tr${rowClass}>`;
            row.forEach(cell => { html += `<${tag}>${cell.trim()}</${tag}>`; });
            html += '</tr>';
          });
          html += '</table></div>';
          result.push(html);
          tableRows = [];
          inTable = false;
        }
      }
      function closeBlockquote() {
        if (inBlockquote) {
          result.push(`<blockquote class="md-blockquote">${blockquoteLines.join('<br>')}</blockquote>`);
          blockquoteLines = [];
          inBlockquote = false;
        }
      }

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        // 테이블 구분선 (---|---|---) → 무시
        if (/^\|?\s*[-:]+(\s*\|\s*[-:]+)+\s*\|?\s*$/.test(trimmed)) {
          continue;
        }

        // 테이블 행
        if (/^\|(.+)\|$/.test(trimmed)) {
          closeList();
          closeBlockquote();
          if (!inTable) inTable = true;
          const cells = trimmed.replace(/^\||\|$/g, '').split('|');
          tableRows.push(cells);
          continue;
        } else if (inTable) {
          closeTable();
        }

        // 블록인용 (> ...)
        if (/^&gt;\s?(.*)/.test(trimmed)) {
          closeList();
          closeTable();
          const content = trimmed.replace(/^&gt;\s?/, '');
          // [!NOTE], [!TIP] 등 GitHub 알림 스타일
          if (/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/.test(content)) {
            const match = content.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)/);
            if (match) {
              const type = match[1].toLowerCase();
              const alertText = match[2] || '';
              const icons = { note: 'ℹ️', tip: '💡', important: '❗', warning: '⚠️', caution: '🚨' };
              // 다음 줄들도 > 로 시작하면 포함
              let body = alertText;
              while (i + 1 < lines.length && /^&gt;\s?/.test(lines[i+1].trim())) {
                i++;
                body += '<br>' + lines[i].trim().replace(/^&gt;\s?/, '');
              }
              result.push(`<div class="md-alert md-alert-${type}"><span class="md-alert-icon">${icons[type]}</span><span class="md-alert-title">${type.toUpperCase()}</span><div class="md-alert-body">${body}</div></div>`);
              continue;
            }
          }
          inBlockquote = true;
          blockquoteLines.push(content);
          continue;
        } else if (inBlockquote) {
          closeBlockquote();
        }

        // 수평선
        if (/^(---|\*\*\*|___)$/.test(trimmed)) {
          closeList(); closeTable(); closeBlockquote();
          result.push('<hr class="md-hr">');
          continue;
        }

        // 헤딩 (### → h3, ## → h2, # → h1)
        const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
        if (headingMatch) {
          closeList(); closeTable(); closeBlockquote();
          const level = headingMatch[1].length;
          result.push(`<h${level} class="md-heading md-h${level}">${headingMatch[2]}</h${level}>`);
          continue;
        }

        // 비순서 목록 (- 또는 * 또는 •)
        const ulMatch = trimmed.match(/^[-*•]\s+(.+)$/);
        if (ulMatch) {
          closeTable(); closeBlockquote();
          if (!inList || listType !== 'ul') {
            closeList();
            result.push('<ul class="md-list">');
            inList = true;
            listType = 'ul';
          }
          // 체크박스 지원
          let content = ulMatch[1];
          if (/^\[x\]\s/.test(content)) {
            content = `<span class="md-checkbox checked">✅</span> ${content.replace(/^\[x\]\s/, '')}`;
          } else if (/^\[ \]\s/.test(content)) {
            content = `<span class="md-checkbox">⬜</span> ${content.replace(/^\[ \]\s/, '')}`;
          } else if (/^\[\/\]\s/.test(content)) {
            content = `<span class="md-checkbox progress">🔄</span> ${content.replace(/^\[\/\]\s/, '')}`;
          }
          result.push(`<li>${content}</li>`);
          continue;
        }

        // 순서 목록 (1. 2. 3.)
        const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
        if (olMatch) {
          closeTable(); closeBlockquote();
          if (!inList || listType !== 'ol') {
            closeList();
            result.push('<ol class="md-list md-ol">');
            inList = true;
            listType = 'ol';
          }
          result.push(`<li>${olMatch[1]}</li>`);
          continue;
        }

        // 일반 텍스트 → 리스트 종료
        if (inList && trimmed === '') {
          closeList();
        }

        // 빈 줄
        if (trimmed === '') {
          closeList(); closeTable(); closeBlockquote();
          result.push('<div class="md-spacer"></div>');
          continue;
        }

        // 일반 텍스트 (인라인 마크다운은 아래서 처리)
        closeList(); closeTable(); closeBlockquote();
        result.push(`<p class="md-p">${trimmed}</p>`);
      }

      closeList(); closeTable(); closeBlockquote();
      text = result.join('\n');

      // ── 6단계: 인라인 마크다운 ──
      // Bold
      text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      // Italic
      text = text.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
      // Strikethrough
      text = text.replace(/~~(.+?)~~/g, '<del>$1</del>');
      // Links [text](url)
      text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, href) => {
        const safeHref = safeMarkdownUrl(href);
        const rel = /^https?:\/\//i.test(safeHref) ? ' rel="noopener noreferrer"' : '';
        return `<a href="${safeHref}" target="_blank" class="md-link"${rel}>${label}</a>`;
      });

      // ── 7단계: 코드블록 복원 ──
      text = text.replace(/%%CODEBLOCK_(\d+)%%/g, (match, idx) => {
        const block = codeBlocks[parseInt(idx)];
        const langLabel = block.lang ? `<span class="code-lang">${block.lang}</span>` : '';
        const escapedCode = block.code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        // Diff 블록 특별 처리
        if (block.lang === 'diff') {
          const diffLines = block.code.split('\n').map(l => {
            const escaped = l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            if (l.startsWith('+')) return `<span class="diff-add">${escaped}</span>`;
            if (l.startsWith('-')) return `<span class="diff-del">${escaped}</span>`;
            return `<span class="diff-ctx">${escaped}</span>`;
          }).join('\n');
          return `<div class="code-block-wrap"><div class="code-block-header">${langLabel}<button class="copy-btn" onclick="navigator.clipboard.writeText(atob('${btoa(unescape(encodeURIComponent(block.code)))}'))">📋 Copy</button></div><pre class="code-block diff-block">${diffLines}</pre></div>`;
        }

        // Mermaid 처리
        if (block.lang === 'mermaid') {
          return `<div class="mermaid">${escapeMarkdownHTML(block.code)}</div>`;
        }

        // Carousel 처리
        if (block.lang === 'carousel') {
          const slides = block.code.split(/<!--\s*slide\s*-->/i);
          let carouselHtml = '<div class="md-carousel-container">';
          slides.forEach(slide => {
             const imagePlaceholders = [];
             let slideHtml = slide.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
               const idx = imagePlaceholders.length;
               const safeSrc = escapeMarkdownHTML(safeCarouselImageSrc(src));
               const safeAlt = escapeMarkdownHTML(alt);
               imagePlaceholders.push(`<img src="${safeSrc}" alt="${safeAlt}" loading="lazy">`);
               return `%%CAROUSEL_IMAGE_${idx}%%`;
             });
             slideHtml = escapeMarkdownHTML(slideHtml);
             slideHtml = slideHtml.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
             slideHtml = slideHtml.replace(/%%CAROUSEL_IMAGE_(\d+)%%/g, (match, idx) => imagePlaceholders[parseInt(idx)] || '');
             slideHtml = slideHtml.replace(/\n/g, '<br>');
             carouselHtml += `<div class="md-carousel-slide">${slideHtml.trim()}</div>`;
          });
          carouselHtml += '</div>';
          return carouselHtml;
        }

        return `<div class="code-block-wrap"><div class="code-block-header">${langLabel}<button class="copy-btn" onclick="navigator.clipboard.writeText(atob('${btoa(unescape(encodeURIComponent(block.code)))}'))">📋 Copy</button></div><pre class="code-block">${escapedCode}</pre></div>`;
      });

      // 인라인 코드 복원
      text = text.replace(/%%INLINE_(\d+)%%/g, (match, idx) => {
        const code = inlineCodes[parseInt(idx)].replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `<code class="inline-code">${code}</code>`;
      });

      // ── 8단계: Tool Call / Response ──
      text = text.replace(/&lt;tool_call&gt;([\s\S]*?)&lt;\/tool_call&gt;/g,
        '<div class="tool-call-box"><div class="tool-header">🔧 Tool Call</div><pre>$1</pre></div>'
      );
      text = text.replace(/&lt;tool_response&gt;([\s\S]*?)&lt;\/tool_response&gt;/g,
        '<div class="tool-result-box"><div class="tool-header">✅ Result</div><pre>$1</pre></div>'
      );

      // ── 9단계: <think> 블록 변환 ──
      // 완전히 닫힌 생각 블록 (생성 완료)
      text = text.replace(/%%THINK_START%%([\s\S]*?)%%THINK_END%%/g,
        '<details class="think-block"><summary>🧠 Thinking Process</summary><div class="think-content">$1</div></details>'
      );

      // 아직 닫히지 않은 생각 블록 (스트리밍 중 또는 중단됨)
      text = text.replace(/%%THINK_START%%([\s\S]*?)(?=%%THINK_START%%|$)/g,
        '<details class="think-block generating" open><summary>🧠 Thinking<span class="typing-indicator" style="margin-left: 8px; height: 12px;"><span></span><span></span><span></span></span></summary><div class="think-content">$1</div></details>'
      );

      // ── 최종 단계: DOMPurify 새니타이제이션 (XSS 방어) ──
      // 에이전트/도구 출력에서 주입될 수 있는 악성 스크립트, 이벤트 핸들러,
      // javascript: URL 등을 제거. 허용되는 태그/속성만 남긴다.
      if (typeof DOMPurify !== 'undefined') {
        text = DOMPurify.sanitize(text, {
          ALLOWED_TAGS: [
            'details', 'summary', 'div', 'section', 'span', 'p', 'br', 'hr',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
            'a', 'img', 'strong', 'em', 'b', 'i', 'u', 's', 'del', 'mark',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'sup', 'sub', 'figure', 'figcaption',
          ],
          ALLOWED_ATTR: [
            'href', 'src', 'alt', 'title', 'class', 'id', 'style',
            'target', 'rel', 'width', 'height', 'colspan', 'rowspan',
            'open', 'loading',
          ],
          ALLOW_DATA_ATTR: false,
          FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus', 'onblur'],
        });
      }

      return text;
    }

    function renderDiffs(container) {
      if (typeof Diff2HtmlUI === 'undefined') return;
      const targets = container.querySelectorAll('.diff-render-target');
      targets.forEach(target => {
        if (target.dataset.rendered === 'true') return;
        try {
          const rawDiff = decodeURIComponent(escape(atob(target.dataset.diffB64)));
          const diff2htmlUi = new Diff2HtmlUI(target, rawDiff, {
            drawFileList: false,
            matching: 'lines',
            outputFormat: 'side-by-side',
            theme: 'dark'
          });
          diff2htmlUi.draw();
          target.dataset.rendered = 'true';
          // Find and hide the fallback pre tag if rendering succeeds
          const fallback = target.nextElementSibling;
          if (fallback && fallback.tagName === 'PRE') {
            fallback.style.display = 'none';
          }
        } catch (e) {
          console.error("Diff render error:", e);
          // Show fallback on error
          const fallback = target.nextElementSibling;
          if (fallback && fallback.tagName === 'PRE') {
            fallback.style.display = 'block';
          }
        }
      });
    }

    // ─── 2. 파일 트리 및 코드 뷰어 기능 ───
    const treeContainer = document.getElementById('file-tree');
    const editorTitle = document.getElementById('editor-title');
    const editorPlaceholder = document.getElementById('editor-placeholder');
    const refreshBtn = document.getElementById('refresh-tree-btn');

    // Monaco 에디터 인스턴스
    let monacoEditor = null;
    let monacoLoaded = false;

    // Monaco Editor 초기화 로직
    if (window.require) {
      require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }});
      require(['vs/editor/editor.main'], function() {
        monacoLoaded = true;

        // Define Antigravity Premium Theme
        monaco.editor.defineTheme('antigravity-dark', {
          base: 'vs-dark',
          inherit: true,
          rules: [
            { background: '12141c' }
          ],
          colors: {
            'editor.background': '#12141c',
            'editor.lineHighlightBackground': '#181b25',
            'editorLineNumber.foreground': '#5f6378',
            'editorIndentGuide.background': '#181b25',
            'editorSuggestWidget.background': '#0a0b10',
            'editorSuggestWidget.border': '#ffffff10'
          }
        });

        monacoEditor = monaco.editor.create(document.getElementById('monaco-editor-container'), {
          value: "",
          language: "plaintext",
          theme: "antigravity-dark",
          automaticLayout: true,
          minimap: { enabled: true, renderCharacters: false, scale: 0.75 },
          fontSize: 13,
          fontFamily: '"JetBrains Mono", "Fira Code", Consolas, "Courier New", monospace',
          readOnly: true,
          wordWrap: 'bounded',
          wordWrapColumn: 120,
          wrappingIndent: 'same',
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          cursorBlinking: 'smooth',
          padding: { top: 16 }
        });
      });
    }

    refreshBtn.addEventListener('click', () => loadDirectory('.'));
    ChatPage.refreshFileTree = () => loadDirectory('.');

    async function loadDirectory(path, containerEl = treeContainer) {
      if (containerEl === treeContainer) {
        containerEl.innerHTML = '<div class="tree-loading">Loading...</div>';
      }

      try {
        const res = await fetch('/api/fs/list?dir=' + encodeURIComponent(path));
        const data = await res.json();

        if (data.ok) {
          containerEl.innerHTML = '';
          const ul = document.createElement('ul');
          ul.className = 'tree-list';

          // VS Code 스타일 SVG 아이콘
          const chevronSVG = `<svg class="chevron-icon" viewBox="0 0 16 16" fill="currentColor" style="width:16px;height:16px;opacity:0.6;transition:transform 0.1s;"><path fill-rule="evenodd" clip-rule="evenodd" d="M10.072 8.024L5.715 3.667l.618-.62L11 7.716v.618L6.333 13l-.618-.619 4.357-4.357z"/></svg>`;
          const fileSVG = `<svg viewBox="0 0 16 16" fill="#519aba" style="width:16px;height:16px;margin-right:6px;"><path d="M13.71 4.29l-3-3L10 1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1V5l-.29-.71zM10 2.41L12.59 5H10V2.41zM13 14H4V2h5v4h4v8z"/></svg>`;
          const folderSVG = `<svg viewBox="0 0 16 16" fill="#dcb67a" style="width:16px;height:16px;margin-right:6px;margin-left:2px;"><path d="M14.5 3L8.646 3 7.146 1.5 1.5 1.5c-.276 0-.5.224-.5.5v12c0 .276.224.5.5.5h13c.276 0 .5-.224.5-.5v-10c0-.276-.224-.5-.5-.5zm-.5 1l-.001 9H2V5h12v-1z"/></svg>`;

          data.items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'tree-item';

            const textSpan = document.createElement('span');
            textSpan.className = 'tree-label';

            textSpan.addEventListener('contextmenu', (e) => {
              e.preventDefault();

              // 기존 메뉴가 있다면 제거
              let oldMenu = document.getElementById('custom-context-menu');
              if (oldMenu) oldMenu.remove();

              // 새 메뉴 생성
              const menu = document.createElement('div');
              menu.id = 'custom-context-menu';
              menu.style.position = 'fixed';
              menu.style.left = `${e.clientX}px`;
              menu.style.top = `${e.clientY}px`;
              menu.style.background = '#252526';
              menu.style.border = '1px solid #454545';
              menu.style.padding = '4px 0';
              menu.style.borderRadius = '4px';
              menu.style.boxShadow = '0 4px 6px rgba(0,0,0,0.3)';
              menu.style.zIndex = '9999';

              const deleteItem = document.createElement('div');
              deleteItem.textContent = '🗑️ Delete';
              deleteItem.style.padding = '8px 16px';
              deleteItem.style.cursor = 'pointer';
              deleteItem.style.color = '#ff6b6b';
              deleteItem.style.fontSize = '13px';

              deleteItem.addEventListener('mouseenter', () => deleteItem.style.background = '#37373d');
              deleteItem.addEventListener('mouseleave', () => deleteItem.style.background = 'transparent');

              deleteItem.addEventListener('click', async () => {
                menu.remove();
                try {
                  const res = await fetch('/api/fs/delete', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: item.path })
                  });
                  const data = await res.json();
                  if (data.ok) {
                    loadDirectory('.');
                  } else {
                    alert('삭제 실패: ' + (data.detail || '오류'));
                  }
                } catch (err) {
                  alert('서버 오류: ' + err.message);
                }
              });

              menu.appendChild(deleteItem);
              document.body.appendChild(menu);

              // 다른 곳 클릭 시 메뉴 닫기
              const closeMenu = () => {
                menu.remove();
                document.removeEventListener('click', closeMenu);
                document.removeEventListener('contextmenu', closeMenu);
              };

              // 약간의 지연을 주어 현재 클릭 이벤트가 닫기 이벤트를 발생시키지 않도록 함
              setTimeout(() => {
                document.addEventListener('click', closeMenu);
                document.addEventListener('contextmenu', closeMenu);
              }, 10);
            });

            if (item.is_dir) {
              textSpan.innerHTML = `${chevronSVG}${folderSVG} ${item.name}`;
              li.classList.add('tree-folder');
              const childrenContainer = document.createElement('div');
              childrenContainer.className = 'tree-children';
              childrenContainer.style.display = 'none';

              textSpan.addEventListener('click', async () => {
                const isExpanded = childrenContainer.style.display === 'block';
                const chevron = textSpan.querySelector('.chevron-icon');
                if (isExpanded) {
                  childrenContainer.style.display = 'none';
                  if(chevron) chevron.style.transform = 'rotate(0deg)';
                } else {
                  childrenContainer.style.display = 'block';
                  if(chevron) chevron.style.transform = 'rotate(90deg)';
                  if (childrenContainer.innerHTML === '') {
                    await loadDirectory(item.path, childrenContainer);
                  }
                }
              });
              li.appendChild(textSpan);
              li.appendChild(childrenContainer);
            } else {
              textSpan.innerHTML = `${fileSVG} <span style="margin-left:2px;">${item.name}</span>`;
              li.classList.add('tree-file');
              textSpan.addEventListener('click', () => {
                document.querySelectorAll('.tree-label.active').forEach(el => el.classList.remove('active'));
                textSpan.classList.add('active');
                loadFileContent(item.path, item.name);
              });
              li.appendChild(textSpan);
            }
            ul.appendChild(li);
          });
          containerEl.appendChild(ul);
        } else {
          containerEl.innerHTML = '<div class="tree-error">Failed to load directory</div>';
        }
      } catch (e) {
        console.error(e);
        containerEl.innerHTML = '<div class="tree-error">Error loading directory</div>';
      }
    }

    // 파일 확장자별 언어 매핑 유틸리티
    function getLanguageFromExt(filename) {
      const ext = filename.split('.').pop().toLowerCase();
      const map = {
        'js': 'javascript', 'ts': 'typescript', 'py': 'python',
        'html': 'html', 'css': 'css', 'json': 'json',
        'md': 'markdown', 'yaml': 'yaml', 'yml': 'yaml',
        'sh': 'shell', 'bash': 'shell', 'xml': 'xml', 'sql': 'sql'
      };
      return map[ext] || 'plaintext';
    }

    async function loadFileContent(filePath, fileName) {
      editorTitle.textContent = fileName;
      if(editorPlaceholder) editorPlaceholder.style.display = 'none';

      try {
        const res = await fetch('/api/fs/read?file=' + encodeURIComponent(filePath));
        const data = await res.json();

        if (data.ok) {
          if (monacoLoaded && monacoEditor) {
            const lang = getLanguageFromExt(fileName);
            monaco.editor.setModelLanguage(monacoEditor.getModel(), lang);
            monacoEditor.setValue(data.content);
          }
        } else {
          if (monacoEditor) monacoEditor.setValue('Error: ' + (data.detail || 'Failed to read file'));
        }
      } catch (e) {
        if (monacoEditor) monacoEditor.setValue('Error: ' + e.message);
      }
    }

    // ─── Workspace Folder Picker 로직 ───
    const openFolderBtn = document.getElementById('open-folder-btn');
    const folderModal = document.getElementById('folder-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const cancelFolderBtn = document.getElementById('cancel-folder-btn');
    const selectFolderBtn = document.getElementById('select-folder-btn');
    const browseList = document.getElementById('browse-list');
    const currentBrowsePath = document.getElementById('current-browse-path');

    let selectedFolderPath = '/';

    async function loadBrowseDirectory(path) {
      try {
        const res = await fetch('/api/fs/browse?dir=' + encodeURIComponent(path));
        const data = await res.json();
        if (data.ok) {
          selectedFolderPath = data.current;
          currentBrowsePath.textContent = data.current;
          browseList.innerHTML = '';

          const ul = document.createElement('ul');
          ul.className = 'tree-list';
          ul.style.paddingLeft = '16px';

          // 상위 폴더로 가기
          if (data.parent) {
            const li = document.createElement('li');
            li.className = 'tree-item tree-folder';
            li.innerHTML = `<span class="tree-label" style="padding: 6px 8px;"><span style="margin-right:6px">📁</span> .. (Up a dir)</span>`;
            li.addEventListener('click', () => loadBrowseDirectory(data.parent));
            ul.appendChild(li);
          }

          data.items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'tree-item tree-folder';
            li.innerHTML = `<span class="tree-label" style="padding: 6px 8px;"><span style="margin-right:6px">📁</span> ${item.name}</span>`;
            li.addEventListener('click', () => loadBrowseDirectory(item.path));
            ul.appendChild(li);
          });

          browseList.appendChild(ul);
        }
      } catch (e) {
        console.error(e);
      }
    }

    let folderModalMode = 'workspace';

    openFolderBtn.addEventListener('click', async () => {
      folderModalMode = 'workspace';
      document.querySelector('#folder-modal h3').textContent = 'Open Workspace Folder';
      document.getElementById('select-folder-btn').textContent = 'Select This Folder';

      const res = await fetch('/api/fs/workspace');
      const data = await res.json();
      const startPath = data.ok ? data.workspace : '/';

      hideAllModals();
      folderModal.style.display = 'flex';
      loadBrowseDirectory(startPath);
    });

    const newFolderBtn = document.getElementById('new-folder-btn');
    const newFolderModal = document.getElementById('new-folder-modal');
    const newFolderInput = document.getElementById('new-folder-input');

    if (newFolderBtn && newFolderModal && newFolderInput) {
      newFolderBtn.addEventListener('click', () => {
        hideAllModals();
        newFolderInput.value = '새 폴더';
        newFolderModal.style.display = 'flex';
        setTimeout(() => newFolderInput.focus(), 100);
      });

      const hideNewFolderModal = () => {
        newFolderModal.style.display = 'none';
      };

      document.getElementById('close-new-folder-btn').addEventListener('click', hideNewFolderModal);
      document.getElementById('cancel-new-folder-btn').addEventListener('click', hideNewFolderModal);

      const doCreateFolder = async () => {
        const folderName = newFolderInput.value.trim();
        if (folderName) {
          try {
            const res = await fetch('/api/fs/mkdir', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: folderName })
            });
            const data = await res.json();
            if (data.ok) {
              hideNewFolderModal();
              loadDirectory('.');
            } else {
              // 커스텀 모달 내의 오류 표시로 대체할 수 있으나, alert의 차단 여부는 환경에 따라 다르므로
              // 여기서는 간단한 UI 업데이트 방식으로 전환하는 것이 더 안전함.
              const label = newFolderModal.querySelector('label');
              const oldText = label.textContent;
              label.textContent = '폴더 생성 실패: ' + (data.detail || data.message || '오류');
              label.style.color = '#ff6b6b';
              setTimeout(() => {
                label.textContent = oldText;
                label.style.color = 'var(--text-secondary)';
              }, 3000);
            }
          } catch (e) {
            console.error('서버 오류: ' + e.message);
          }
        }
      };

      document.getElementById('confirm-new-folder-btn').addEventListener('click', doCreateFolder);
      newFolderInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doCreateFolder();
        if (e.key === 'Escape') hideNewFolderModal();
      });
    }

    const indexWorkspaceBtn = document.getElementById('index-workspace-btn');
    if (indexWorkspaceBtn) {
      indexWorkspaceBtn.addEventListener('click', async () => {
        folderModalMode = 'index';
        document.querySelector('#folder-modal h3').textContent = 'Select Folder to Index (LLM Wiki)';
        document.getElementById('select-folder-btn').textContent = 'Index This Folder';

        const res = await fetch('/api/fs/workspace');
        const data = await res.json();
        const startPath = data.ok ? data.workspace : '/';

        folderModal.style.display = 'flex';
        loadBrowseDirectory(startPath);
      });
    }

    const hideModal = () => folderModal.style.display = 'none';
    closeModalBtn.addEventListener('click', hideModal);
    cancelFolderBtn.addEventListener('click', hideModal);

    selectFolderBtn.addEventListener('click', async () => {
      if (folderModalMode === 'workspace') {
        try {
          const res = await fetch('/api/fs/workspace', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: selectedFolderPath })
          });
          const data = await res.json();
          if (data.ok) {
            hideModal();
            localStorage.setItem('antigravity_last_workspace', data.workspace);
            // Wiki (LLM Wiki) vault 경로도 동기화
            localStorage.setItem('antigravity_vault_path', data.workspace);
            fetch('/api/vault/config', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ vault_path: data.workspace })
            }).catch(e => console.warn('Vault sync failed:', e));
            loadDirectory('.');
            currentWorkspacePath = data.workspace;
            await loadChatHistory();
            editorTitle.textContent = "Welcome";
            if (monacoEditor) monacoEditor.setValue("");
            if(editorPlaceholder) editorPlaceholder.style.display = 'block';
          } else {
            alert('Failed to set workspace: ' + data.detail);
          }
        } catch (e) {
          alert('Error: ' + e.message);
        }
      } else if (folderModalMode === 'index') {
        try {
          selectFolderBtn.disabled = true;
          selectFolderBtn.textContent = 'Starting...';

          const res = await fetch('/api/workspace/ingest?path=' + encodeURIComponent(selectedFolderPath), {
            method: 'POST'
          });
          const data = await res.json();
          if (res.ok) {
            hideModal();
            alert(`[학습 시작] 선택하신 폴더(${selectedFolderPath})의 전체 파일을 백그라운드에서 읽어들이기 시작했습니다.\\n완료 후 에이전트가 이를 기억하고 참고합니다.`);
          } else {
            alert('학습 시작 실패: ' + (data.detail || data.message || '알 수 없는 오류'));
          }
        } catch (e) {
          console.error(e);
          alert('서버 연결 오류');
        } finally {
          selectFolderBtn.disabled = false;
          selectFolderBtn.textContent = 'Index This Folder';
        }
      }
    });

    // ─── 3. 창 분할 (Split.js) ───
    let splitInstance = null;
    function initSplitJs() {
      if (typeof Split !== 'undefined') {
        // 모바일에서는 Split.js 비활성화
        if (window.innerWidth <= 768) {
          if (splitInstance) {
            splitInstance.destroy();
            splitInstance = null;
          }
          return;
        }

        if (splitInstance) return; // 이미 활성화됨

        let savedSizes = [20, 50, 30];
        try {
          const stored = localStorage.getItem('ide_split_sizes_v5');
          if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed) && parsed.length === 3) {
              savedSizes = parsed;
            }
          }
        } catch(e) { console.warn("Failed to load split sizes", e); }

        splitInstance = Split(['#ide-explorer', '.ide-editor', '.ide-chat'], {
          sizes: savedSizes,
          minSize: [150, 300, 300],
          gutterSize: 6,
          cursor: 'col-resize',
          onDragEnd: () => {
            localStorage.setItem('ide_split_sizes_v5', JSON.stringify(splitInstance.getSizes()));
            // Monaco 에디터 사이즈 자동 재계산 유도
            if (monacoEditor) monacoEditor.layout();
          }
        });
      }
    }

    // 초기 실행 및 리사이즈 이벤트 바인딩
    initSplitJs();
    window.addEventListener('resize', initSplitJs);

    // ─── 모바일 햄버거 메뉴 오프캔버스 로직 ───
    const mobileHamburgerBtn = document.getElementById('mobile-hamburger-btn');
    const explorerOverlay = document.getElementById('explorer-overlay');
    const ideExplorer = document.getElementById('ide-explorer');

    if (mobileHamburgerBtn) {
      mobileHamburgerBtn.addEventListener('click', () => {
        ideExplorer.classList.add('open');
        explorerOverlay.classList.add('open');
      });
    }

    if (explorerOverlay) {
      explorerOverlay.addEventListener('click', () => {
        ideExplorer.classList.remove('open');
        explorerOverlay.classList.remove('open');
      });
    }

    const mobileCommandPaletteBtn = document.getElementById('mobile-command-palette-btn');
    if (mobileCommandPaletteBtn) {
      mobileCommandPaletteBtn.addEventListener('click', () => {
        window.openCommandPalette?.();
      });
    }

    // 모바일에서 새 채팅 생성 버튼
    const mobileNewChatBtn = document.getElementById('mobile-new-chat-btn');
    if (mobileNewChatBtn) {
      mobileNewChatBtn.addEventListener('click', () => {
        document.getElementById('new-chat-btn')?.click();
      });
    }

    // 초기화 로직: 로컬 스토리지에 저장된 마지막 워크스페이스 복구 시도
    const lastWorkspace = localStorage.getItem('antigravity_last_workspace');

    const initWorkspace = async () => {
      try {
        if (lastWorkspace) {
          // 저장된 워크스페이스가 있다면 복구 시도
          const res = await fetch('/api/fs/workspace', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: lastWorkspace })
          });
          const data = await res.json();
          if (data.ok) {
            currentWorkspacePath = data.workspace;
            // Wiki vault 경로도 동기화
            localStorage.setItem('antigravity_vault_path', data.workspace);
          }
        } else {
          // 없으면 현재 백엔드 설정 가져오기
          const res = await fetch('/api/fs/workspace');
          const data = await res.json();
          if (data.ok) {
            currentWorkspacePath = data.workspace;
            // Wiki vault 경로도 동기화
            localStorage.setItem('antigravity_vault_path', data.workspace);
          }
        }
      } catch (e) {
        console.error("Failed to initialize workspace path:", e);
      } finally {
        loadDirectory('.');
        await loadChatHistory();
        checkActiveAgent();
      }
    };

    async function checkActiveAgent() {
      try {
        const res = await fetch('/api/agent/active');
        const data = await res.json();
        if (data.active) {
          console.log("Found active agent session, reconnecting...");
          // Render the history provided
          if (data.history && data.history.length > 0) {
            const historyContent = data.history.join('');
            chatMessages.push({role: "assistant", content: historyContent});
            renderChatMessages();

            // Reconnect to SSE for remaining stream
            const historyDiv = document.getElementById('chat-history');
            const msgs = historyDiv.querySelectorAll('.message.assistant');
            const lastMsgDiv = msgs[msgs.length - 1];
            if (lastMsgDiv) {
              const contentSpan = lastMsgDiv.querySelector('.bubble');
              const generatingBadgeHTML = '<span class="generating-badge">Generating<span class="dots"><span>.</span><span>.</span><span>.</span></span></span>';
              contentSpan.innerHTML += generatingBadgeHTML;

              const reconnectRes = await fetch('/v1/chat/completions/reconnect');
              const reader = reconnectRes.body.getReader();
              const decoder = new TextDecoder("utf-8");

              let buffer = '';
              let assistantContent = historyContent;
              const assistantMsgIndex = chatMessages.length - 1;

              while (true) {
                const { done, value } = await reader.read();
                if (done) {
                  chatMessages[assistantMsgIndex].content = assistantContent;
                  saveChatHistory();
                  contentSpan.innerHTML = formatContent(assistantContent);
                  if (ChatPage.refreshFileTree) ChatPage.refreshFileTree();
                  renderDiffs(lastMsgDiv);
                  break;
                }

                buffer += decoder.decode(value, { stream: true });
                let eolIndex;
                while ((eolIndex = buffer.indexOf('\n')) >= 0) {
                  const line = buffer.slice(0, eolIndex).trim();
                  buffer = buffer.slice(eolIndex + 1);

                  if (line.startsWith('data: ') && line !== 'data: [DONE]') {
                    try {
                      const d = JSON.parse(line.slice(6));
                      if (d.choices && d.choices[0].delta && d.choices[0].delta.content) {
                        assistantContent += d.choices[0].delta.content;
                        contentSpan.innerHTML = formatContent(assistantContent) + generatingBadgeHTML;
                        history.scrollTop = history.scrollHeight;
                      }
                    } catch (e) {}
                  }
                }
              }
            }
          }
        }
      } catch (e) {
        console.error("Failed to check active agent:", e);
      }
    }

    initWorkspace();

    // ─── 3. Plan Mode Toggle ───
    const planToggle = document.getElementById('plan-toggle');
    const planModelName = document.getElementById('plan-bar-model-name');

    // localStorage에서 저장된 상태 복원
    if (localStorage.getItem('antigravity_plan_mode') === 'true') {
      planToggle.classList.add('active');
    }

    // ─── 4. Auto Mode Toggle ───
    const autoToggle = document.getElementById('auto-toggle');
    if (localStorage.getItem('antigravity_auto_mode') === 'true') {
      autoToggle.classList.add('active');
    }

    // ─── 5. TDD Mode Toggle ───
    const tddToggle = document.getElementById('tdd-toggle');
    if (localStorage.getItem('antigravity_tdd_mode') === 'true') {
      tddToggle.classList.add('active');
    }

    tddToggle.addEventListener('click', () => {
      tddToggle.classList.toggle('active');
      const isActive = tddToggle.classList.contains('active');
      localStorage.setItem('antigravity_tdd_mode', isActive);

      if (isActive && window.showToast) {
        window.showToast('🧪 TDD Mode Enabled', 'success');
      }
    });

    planToggle.addEventListener('click', () => {
      planToggle.classList.toggle('active');
      const isActive = planToggle.classList.contains('active');
      localStorage.setItem('antigravity_plan_mode', isActive);
      if (isActive) {
        window.showToast?.('📋 Plan Mode 활성화: AI가 먼저 구현 계획을 수립합니다', 'info');
      } else {
        window.showToast?.('⚡ Direct Mode: AI가 즉시 실행합니다', 'info');
      }
    });

    autoToggle.addEventListener('click', () => {
      autoToggle.classList.toggle('active');
      const isActive = autoToggle.classList.contains('active');
      localStorage.setItem('antigravity_auto_mode', isActive);
      if (isActive) {
        window.showToast?.('🤖 자율 모드 활성화: AI가 툴을 자율적으로 실행합니다', 'success');
      } else {
        window.showToast?.('🤖 자율 모드 해제: 수동 승인 모드', 'info');
      }
    });

    // Self-Test trigger (Cmd+Shift+T)
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 't') {
        e.preventDefault();
        runSelfTest();
      }
    });

    async function runSelfTest() {
      window.showToast?.('🧪 Self-Test 시작: 시스템을 자가 진단합니다...', 'info');
      try {
        const res = await fetch('/api/agent/tools/browser/self-test', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          const r = data.report;
          const passRate = r.pass_rate || '0%';
          if (r.failed === 0) {
            window.showToast?.(`✅ Self-Test 완료: ${r.total}개 전체 통과 (${passRate})`, 'success');
          } else {
            window.showToast?.(`⚠️ Self-Test 완료: ${r.passed}/${r.total} 통과, ${r.failed} 실패`, 'error');
          }
          // 마크다운 리포트를 채팅창에 표시
          if (data.markdown) {
            appendMessage('assistant', formatContent(data.markdown), true);
            history.scrollTop = history.scrollHeight;
          }
        } else {
          window.showToast?.('❌ Self-Test 실패', 'error');
        }
      } catch (e) {
        window.showToast?.('❌ Self-Test 오류: ' + e.message, 'error');
      }
    }
    // Expose globally for command palette
    window.runSelfTest = runSelfTest;

    // Autonomous QA Full Loop (Cmd+Shift+Q)
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'q') {
        e.preventDefault();
        runAutonomousQA();
      }
    });

    async function runAutonomousQA() {
      window.showToast?.('🤖 Autonomous QA 시작: 비전 분석 → 자동 수정 → 검증 루프...', 'info');
      appendMessage('assistant', formatContent('## 🤖 Autonomous QA 루프 시작\n비전 분석 → 코드 수정 → 재테스트 → 검증 루프를 실행합니다...\n\n*이 작업은 수 분이 소요될 수 있습니다.*'), true);
      history.scrollTop = history.scrollHeight;

      try {
        const res = await fetch('/api/agent/tools/browser/autonomous-qa', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ url: window.location.origin, max_iterations: 3 })
        });
        const data = await res.json();
        if (data.ok) {
          const r = data.report;
          const statusIcon = r.status === 'fixed' || r.status === 'no_issues' ? '✅' : '⚠️';
          window.showToast?.(`${statusIcon} Autonomous QA 완료: ${r.total_defects_found}개 결함 발견, ${r.total_resolved}개 해결`,
            r.status === 'fixed' || r.status === 'no_issues' ? 'success' : 'error');
          if (data.markdown) {
            appendMessage('assistant', formatContent(data.markdown), true);
            history.scrollTop = history.scrollHeight;
          }
        } else {
          window.showToast?.('❌ Autonomous QA 실패', 'error');
        }
      } catch (e) {
        window.showToast?.('❌ Autonomous QA 오류: ' + e.message, 'error');
      }
    }
    window.runAutonomousQA = runAutonomousQA;

    // 모델 선택 변경 시 Plan bar 모델명 업데이트
    modelSelect.addEventListener('change', () => {
      const selectedText = modelSelect.options[modelSelect.selectedIndex].text;
      planModelName.textContent = selectedText;
    });

    // ─── 4. Agent Manager Panel ───
    const agentMgrBtn = document.getElementById('open-agent-mgr-btn');
    const agentMgrPanel = document.getElementById('agent-manager-panel');
    const agentMgrOverlay = document.getElementById('agent-manager-overlay');
    const closeAgentMgrBtn = document.getElementById('close-agent-mgr-btn');
    const agentMgrBody = document.getElementById('agent-manager-body');
    const agentMgrProject = document.getElementById('agent-manager-project');

    function getAgentWorkspaceQuery() {
      if (!currentWorkspacePath || currentWorkspacePath === '/') return '';
      return '?workspace=' + encodeURIComponent(currentWorkspacePath);
    }

    function normalizeAgentPath(path) {
      return String(path || '').replace(/\/+$/, '');
    }

    function filterAgentTasksForWorkspace(tasks) {
      if (!currentWorkspacePath || currentWorkspacePath === '/') return tasks;
      const workspace = normalizeAgentPath(currentWorkspacePath);
      return tasks.filter(task => normalizeAgentPath(task.project_path) === workspace);
    }

    function updateAgentManagerProjectLabel() {
      if (!agentMgrProject) return;
      if (!currentWorkspacePath || currentWorkspacePath === '/') {
        agentMgrProject.textContent = '전체 프로젝트';
        return;
      }
      const parts = currentWorkspacePath.split(/[\\/]/).filter(Boolean);
      const name = parts[parts.length - 1] || currentWorkspacePath;
      agentMgrProject.textContent = `${name} · ${currentWorkspacePath}`;
      agentMgrProject.title = currentWorkspacePath;
    }

    function openAgentManager() {
      agentMgrPanel.classList.add('open');
      agentMgrOverlay.classList.add('open');
      updateAgentManagerProjectLabel();
      fetchAgentTasks();
    }

    function closeAgentManager() {
      agentMgrPanel.classList.remove('open');
      agentMgrOverlay.classList.remove('open');
    }

    agentMgrBtn.addEventListener('click', openAgentManager);
    closeAgentMgrBtn.addEventListener('click', closeAgentManager);
    agentMgrOverlay.addEventListener('click', closeAgentManager);

    const mobileAgentMgrBtn = document.getElementById('mobile-agent-mgr-btn');
    if (mobileAgentMgrBtn) {
      mobileAgentMgrBtn.addEventListener('click', openAgentManager);
    }

    function renderAgentTasks(tasks) {
      if (!tasks || tasks.length === 0) {
        agentMgrBody.innerHTML = `
          <div class="agent-manager-empty">
            <span class="empty-icon">🤖</span>
            <span>실행 중인 에이전트가 없습니다</span>
          </div>
        `;
        return;
      }

      agentMgrBody.innerHTML = tasks.map(task => {
        const statusMap = {
          'in_progress': { cls: 'running', icon: '🟢', label: '실행 중' },
          'todo': { cls: 'pending', icon: '⏳', label: '대기 중' },
          'completed': { cls: 'completed', icon: '✅', label: '완료' },
          'cancelled': { cls: 'cancelled', icon: '🛑', label: '취소됨' }
        };
        const st = statusMap[task.status] || { cls: 'pending', icon: '❓', label: task.status };
        const cancelBtn = (task.status === 'in_progress' || task.status === 'todo')
          ? `<button class="task-cancel-btn" data-task-id="${task.id}">🛑 중단</button>`
          : '';
        const removeBtn = (task.status === 'completed' || task.status === 'cancelled')
          ? `<button class="task-remove-btn" data-task-id="${task.id}">정리</button>`
          : '';

        return `
          <div class="agent-task-item">
            <div class="task-title">
              <span>${st.icon}</span>
              <span>${escapeHTML(task.title || 'Untitled Task')}</span>
            </div>
            <div class="task-meta">
              <span class="task-status ${st.cls}">${st.label}</span>
              ${task.project_name ? `<span class="task-project">${escapeHTML(task.project_name)}</span>` : ''}
              ${cancelBtn}
              ${removeBtn}
            </div>
          </div>
        `;
      }).join('');

      // 취소 버튼 이벤트 바인딩
      agentMgrBody.querySelectorAll('.task-cancel-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const taskId = btn.getAttribute('data-task-id');
          btn.disabled = true;
          btn.textContent = '처리 중...';
          try {
            await fetch(`/api/kanban/tasks/${taskId}/cancel`, { method: 'POST' });
            fetchAgentTasks();
          } catch (err) {
            btn.disabled = false;
            btn.textContent = '🛑 중단';
          }
        });
      });

      agentMgrBody.querySelectorAll('.task-remove-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const taskId = btn.getAttribute('data-task-id');
          btn.disabled = true;
          btn.textContent = '정리 중...';
          try {
            await fetch(`/api/kanban/tasks/${taskId}`, { method: 'DELETE' });
            fetchAgentTasks();
          } catch (err) {
            btn.disabled = false;
            btn.textContent = '정리';
          }
        });
      });
    }

    async function fetchAgentTasks() {
      try {
        const res = await fetch('/api/kanban/tasks' + getAgentWorkspaceQuery());
        const data = await res.json();
        renderAgentTasks(data.data || []);
      } catch (err) {
        agentMgrBody.innerHTML = '<div class="agent-manager-empty"><span>❗ 태스크 목록을 불러올 수 없습니다</span></div>';
      }
    }

    // WebSocket 실시간 업데이트
    try {
      const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const agentWs = new WebSocket(`${wsProtocol}//${location.host}/ws/kanban`);
      agentWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const tasks = Array.isArray(data.tasks) ? data.tasks : null;
          if (tasks && agentMgrPanel.classList.contains('open')) {
            renderAgentTasks(filterAgentTasksForWorkspace(tasks));
          }
        } catch (e) {}
      };
      agentWs.onerror = () => console.warn('Agent Manager WebSocket error');
    } catch (e) {
      console.warn('WebSocket not available for Agent Manager');
    }
  }
};
