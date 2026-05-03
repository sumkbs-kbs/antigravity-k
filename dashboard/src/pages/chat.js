export const ChatPage = {
  render: () => `
    <div class="ide-layout">
      <!-- 왼쪽: 파일 탐색기 -->
      <div class="ide-explorer glass-panel">
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

    function loadChatHistory() {
      const saved = localStorage.getItem('antigravity_chat_' + currentWorkspacePath);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            // Migration from single array to multi-session
            activeSessionId = generateSessionId();
            chatMessages = parsed;
            chatSessions = [{
              id: activeSessionId,
              title: chatMessages.length > 0 ? (chatMessages[0].content.substring(0, 15) + '...') : "Migrated Chat",
              updatedAt: new Date().toISOString(),
              messages: chatMessages
            }];
            saveChatHistory();
          } else {
            chatSessions = parsed.sessions || [];
            activeSessionId = parsed.activeSessionId;
            const session = chatSessions.find(s => s.id === activeSessionId);
            chatMessages = session ? session.messages : [];
          }
        } catch(e) {
          console.error("Failed to parse chat history:", e);
          chatSessions = [];
          createNewSession();
        }
      } else {
        chatSessions = [];
        createNewSession();
      }
      if (!activeSessionId) {
        createNewSession();
      } else {
        renderChatMessages();
      }
    }

    function renderChatMessages() {
      history.innerHTML = '';
      if (chatMessages.length === 0) {
        appendMessage('assistant', 'Welcome to Vibe Coding Agent! I am ready to help you with your project. What would you like to build?', true);
      } else {
        chatMessages.forEach(msg => {
          appendMessage(msg.role, msg.role === 'assistant' ? formatContent(msg.content) : msg.content, true);
        });
      }
      history.scrollTop = history.scrollHeight;
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
        
        const dateStr = new Date(session.updatedAt).toLocaleString();
        
        div.innerHTML = `
          <div class="history-title">${escapeHTML(session.title)}</div>
          <div class="history-date">${dateStr}</div>
        `;
        
        div.addEventListener('click', () => {
          activeSessionId = session.id;
          chatMessages = session.messages;
          saveChatHistory();
          renderChatMessages();
          historyModal.style.display = 'none';
        });
        
        chatHistoryList.appendChild(div);
      });
    }

    if (newChatBtn) {
      newChatBtn.addEventListener('click', createNewSession);
    }
    
    if (historyBtn) {
      historyBtn.addEventListener('click', () => {
        renderHistoryModal();
        historyModal.style.display = 'flex';
      });
    }
    
    if (closeHistoryModalBtn) {
      closeHistoryModalBtn.addEventListener('click', () => {
        historyModal.style.display = 'none';
      });
    }

    fetch('/v1/models')
      .then(res => res.json())
      .then(data => {
        if (data && data.data && data.data.length > 0) {
          modelSelect.innerHTML = '';
          data.data.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.id;
            modelSelect.appendChild(option);
          });
        }
      })
      .catch(err => console.error("Failed to load models:", err));
    
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

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !isComposing && !e.isComposing) {
        e.preventDefault();
        sendMessage();
      }
    });

    sendBtn.addEventListener('click', sendMessage);

    async function sendMessage() {
      const text = input.value.trim();
      if (!text) return;
      
      appendMessage('user', text, false);
      chatMessages.push({role: "user", content: text});
      saveChatHistory();

      input.value = '';
      input.style.height = 'auto';
      sendBtn.classList.remove('active');
      
      const model = document.getElementById('model-select').value;
      const assistantMsgDiv = appendMessage('assistant', '<span class="typing-indicator"><span></span><span></span><span></span></span>', false);
      
      try {
        const payload = {
          model: model,
          messages: chatMessages,
          stream: true,
          agent_mode: true
        };
        
        const response = await fetch('/v1/chat/completions', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error('Network response was not ok');
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let assistantContent = '';
        const contentSpan = assistantMsgDiv.querySelector('.bubble');
        contentSpan.innerHTML = ''; 
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            chatMessages.push({role: "assistant", content: assistantContent});
            saveChatHistory();
            
            // 채팅 완료 시 파일 트리 자동 새로고침 및 디프 렌더링
            loadDirectory(".");
            renderDiffs(assistantMsgDiv);
            break;
          }
          
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ') && line !== 'data: [DONE]') {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.choices && data.choices[0].delta && data.choices[0].delta.content) {
                  assistantContent += data.choices[0].delta.content;
                  contentSpan.innerHTML = formatContent(assistantContent);
                  history.scrollTop = history.scrollHeight;
                }
              } catch (e) {}
            }
          }
        }
      } catch (err) {
        console.error(err);
        assistantMsgDiv.querySelector('.bubble').innerHTML = '<span class="error-text">API 요청 중 오류가 발생했습니다: ' + err.message + '</span>';
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
      return msgDiv;
    }
    
    function escapeHTML(str) {
      return str.replace(/[&<>'"]/g, 
        tag => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[tag])
      ).replace(/\n/g, '<br>');
    }
    
    function formatContent(str) {
      // ── 1단계: HTML 이스케이프 (raw text 보호) ──
      let text = str;

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

      // ── 3단계: HTML 이스케이프 ──
      text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

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
      text = text.replace(/📊 \*\*\[Token Usage\]\*\* In: (\d+) tokens \| Out: (\d+) tokens/g,
        '<div class="tool-timeline-badge token"><span class="icon">📊</span> <span class="text"><b>Tokens Used:</b> <span class="token-val">In: $1</span> | <span class="token-val">Out: $2</span></span></div>'
      );
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
      text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="md-link">$1</a>');

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
        monacoEditor = monaco.editor.create(document.getElementById('monaco-editor-container'), {
          value: "",
          language: "plaintext",
          theme: "vs-dark",
          automaticLayout: true,
          minimap: { enabled: true },
          fontSize: 13,
          fontFamily: '"JetBrains Mono", Consolas, "Courier New", monospace',
          readOnly: true
        });
      });
    }

    refreshBtn.addEventListener('click', () => loadDirectory('.'));

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
              textSpan.innerHTML = `<span style="width:16px;display:inline-block"></span>${fileSVG} ${item.name}`;
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
      
      folderModal.style.display = 'flex';
      loadBrowseDirectory(startPath);
    });

    const newFolderBtn = document.getElementById('new-folder-btn');
    const newFolderModal = document.getElementById('new-folder-modal');
    const newFolderInput = document.getElementById('new-folder-input');
    
    if (newFolderBtn && newFolderModal && newFolderInput) {
      newFolderBtn.addEventListener('click', () => {
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
            loadChatHistory();
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
    if (typeof Split !== 'undefined') {
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

      const splitInstance = Split(['.ide-explorer', '.ide-editor', '.ide-chat'], {
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
        loadChatHistory();
      }
    };
    
    initWorkspace();
  }
};
