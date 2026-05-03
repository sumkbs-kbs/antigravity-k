/**
 * Wiki Page — LLM Wiki (Vault Integration)
 * ==========================================
 * 실제 VaultEngine API와 연동하여 문서 트리, 읽기/쓰기, 검색, AI 채팅 참조 기능 제공
 * Chat 페이지와 동일 localStorage 키로 workspace 공유
 */

// localStorage 키: Chat 페이지와 동일하게 사용
const VAULT_PATH_KEY = 'antigravity_vault_path';

// ─── 간단 마크다운 → HTML 변환 ──────────────────────────────────
function renderMarkdown(md) {
  if (!md) return '<p style="color:var(--text-muted);">내용이 없습니다.</p>';
  let html = md
    .replace(/^#### (.+)$/gm, '<h4 class="md-heading md-h4">$1</h4>')
    .replace(/^### (.+)$/gm, '<h3 class="md-heading md-h3">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="md-heading md-h2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="md-heading md-h1">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="md-link" target="_blank">$1</a>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^---$/gm, '<hr class="md-hr">')
    .replace(/\n\n/g, '</p><p class="md-p">')
    .replace(/\n/g, '<br>');
  html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul class="md-list">$1</ul>');
  return `<div class="md-p">${html}</div>`;
}

// ─── 트리 노드 렌더링 ──────────────────────────────────────────
function renderTreeNodes(items, depth = 0) {
  if (!items || items.length === 0) return '';
  const indent = depth * 16;
  return items.map(item => {
    if (item.type === 'folder') {
      const childrenHtml = renderTreeNodes(item.children || [], depth + 1);
      return `
        <div class="wiki-tree-node">
          <div class="tree-item folder" data-path="${item.path}" style="padding-left:${12 + indent}px;">
            <span class="tree-icon">📁</span>
            <span class="tree-name">${item.name}</span>
            <span style="margin-left:auto;font-size:11px;color:var(--text-muted);">${(item.children || []).length}</span>
          </div>
          <div class="tree-children" style="display:none;">
            ${childrenHtml}
          </div>
        </div>`;
    } else {
      return `
        <div class="tree-item file" data-path="${item.path}" style="padding-left:${12 + indent}px;">
          <span class="tree-icon">📄</span>
          <span class="tree-name">${item.name}</span>
        </div>`;
    }
  }).join('');
}

export const WikiPage = () => {
  const container = document.createElement('div');
  container.className = 'page-container full-height-page';
  container.innerHTML = `
    <div class="wiki-layout">
      <!-- 사이드바: 문서 트리 + 검색 + 새 문서 -->
      <div class="wiki-sidebar glass-panel">
        <div class="wiki-sidebar-header">
          <h3 style="font-size:14px;">📚 Wiki</h3>
          <div style="display:flex; gap:4px;">
            <button id="wiki-folder-btn" class="glass-btn small" title="Vault 폴더 변경">📂</button>
            <button id="wiki-new-btn" class="glass-btn small" title="새 문서 생성">+</button>
          </div>
        </div>
        <!-- 현재 Vault 경로 표시 -->
        <div id="wiki-vault-path" style="padding:4px 12px;font-size:11px;color:var(--text-muted);background:rgba(0,0,0,0.15);border-bottom:1px solid var(--glass-border);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer;" title="클릭하여 경로 변경">
          📁 로딩 중...
        </div>
        <div style="padding:8px 12px;">
          <input id="wiki-search-input" class="glass-input full-width" placeholder="🔍 문서 검색..." style="font-size:12px; padding:6px 10px;">
        </div>
        <div id="wiki-tree" class="wiki-tree" style="flex:1;overflow-y:auto;padding:4px 0;">
          <div style="text-align:center;padding:40px 20px;color:var(--text-muted);font-size:13px;">
            로딩 중...
          </div>
        </div>
      </div>

      <!-- 메인 콘텐츠: 문서 뷰/편집 -->
      <div class="wiki-content glass-panel">
        <div class="wiki-content-header">
          <div id="wiki-breadcrumb" class="breadcrumb" style="font-size:12px;">문서를 선택하세요</div>
          <div id="wiki-actions" class="wiki-actions" style="display:flex;gap:6px;">
            <button id="wiki-chat-ref-btn" class="glass-btn small" title="AI 채팅에서 이 문서 참조" style="display:none;">💬 채팅 참조</button>
            <button id="wiki-edit-btn" class="glass-btn small" style="display:none;">✏️ 편집</button>
            <button id="wiki-save-btn" class="glass-btn small primary" style="display:none;">💾 저장</button>
            <button id="wiki-cancel-btn" class="glass-btn small" style="display:none;">취소</button>
          </div>
        </div>
        <div id="wiki-body" class="wiki-markdown-body" style="flex:1;overflow-y:auto;padding:24px 32px;">
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:12px;color:var(--text-muted);">
            <span style="font-size:48px;opacity:0.3;">📚</span>
            <p style="font-size:14px;">왼쪽 트리에서 문서를 선택하거나 새 문서를 생성하세요.</p>
            <p style="font-size:12px;color:var(--text-muted);">📂 버튼으로 Wiki 폴더를 지정할 수 있습니다.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 폴더 변경 모달 -->
    <div id="wiki-folder-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content glass-panel" style="width:500px;max-height:70vh;display:flex;flex-direction:column;">
        <div style="padding:14px 16px;border-bottom:1px solid var(--glass-border);display:flex;justify-content:space-between;align-items:center;">
          <h3 style="margin:0;font-size:14px;">📂 Vault 폴더 변경</h3>
          <button id="wiki-folder-close" class="icon-btn">✕</button>
        </div>
        <div style="padding:12px 16px;">
          <label style="display:block;font-size:12px;color:var(--text-secondary);margin-bottom:6px;">
            Wiki/Vault 문서가 저장될 폴더의 절대 경로를 입력하세요.
            <br><span style="font-size:11px;color:var(--text-muted);">AI 채팅의 파일 탐색기와 동일한 프로젝트를 참조합니다.</span>
          </label>
          <input id="wiki-folder-input" class="glass-input full-width" placeholder="/Users/.../my-vault" style="font-size:13px;">
          <div id="wiki-folder-current" style="margin-top:8px;font-size:11px;color:var(--text-muted);"></div>
        </div>
        <div style="padding:12px 16px;border-top:1px solid var(--glass-border);display:flex;justify-content:flex-end;gap:8px;">
          <button id="wiki-folder-cancel" class="glass-btn small">취소</button>
          <button id="wiki-folder-confirm" class="glass-btn small primary">적용</button>
        </div>
      </div>
    </div>

    <!-- 새 문서 생성 모달 -->
    <div id="wiki-new-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content glass-panel" style="width:440px;">
        <div style="padding:14px 16px;border-bottom:1px solid var(--glass-border);display:flex;justify-content:space-between;align-items:center;">
          <h3 style="margin:0;font-size:14px;">📝 새 문서 생성</h3>
          <button id="wiki-new-close" class="icon-btn">✕</button>
        </div>
        <div style="padding:16px;display:flex;flex-direction:column;gap:12px;">
          <div>
            <label style="display:block;font-size:12px;color:var(--text-secondary);margin-bottom:4px;">파일 경로 (vault 기준)</label>
            <input id="wiki-new-path" class="glass-input full-width" placeholder="예: notes/my-note.md" style="font-size:13px;">
          </div>
          <div>
            <label style="display:block;font-size:12px;color:var(--text-secondary);margin-bottom:4px;">제목</label>
            <input id="wiki-new-title" class="glass-input full-width" placeholder="문서 제목" style="font-size:13px;">
          </div>
          <div>
            <label style="display:block;font-size:12px;color:var(--text-secondary);margin-bottom:4px;">태그 (쉼표로 구분)</label>
            <input id="wiki-new-tags" class="glass-input full-width" placeholder="architecture, notes" style="font-size:13px;">
          </div>
        </div>
        <div style="padding:12px 16px;border-top:1px solid var(--glass-border);display:flex;justify-content:flex-end;gap:8px;">
          <button id="wiki-new-cancel" class="glass-btn small">취소</button>
          <button id="wiki-new-confirm" class="glass-btn small primary">생성</button>
        </div>
      </div>
    </div>
  `;

  // ─── State ────────────────────────────────────────────────────
  let currentPath = null;
  let currentContent = '';
  let currentMetadata = {};
  let currentVaultPath = '';
  let isEditing = false;

  // ─── DOM Refs ────────────────────────────────────────────────
  const treeEl = container.querySelector('#wiki-tree');
  const bodyEl = container.querySelector('#wiki-body');
  const breadcrumb = container.querySelector('#wiki-breadcrumb');
  const vaultPathEl = container.querySelector('#wiki-vault-path');
  const searchInput = container.querySelector('#wiki-search-input');
  const editBtn = container.querySelector('#wiki-edit-btn');
  const saveBtn = container.querySelector('#wiki-save-btn');
  const cancelBtn = container.querySelector('#wiki-cancel-btn');
  const chatRefBtn = container.querySelector('#wiki-chat-ref-btn');
  const newBtn = container.querySelector('#wiki-new-btn');
  const newModal = container.querySelector('#wiki-new-modal');
  const folderBtn = container.querySelector('#wiki-folder-btn');
  const folderModal = container.querySelector('#wiki-folder-modal');

  // ─── 0. Vault 경로 초기화 (localStorage에서 복원 or 서버 기본값) ──
  async function initVaultPath() {
    const savedPath = localStorage.getItem(VAULT_PATH_KEY);
    
    if (savedPath) {
      // 저장된 경로가 있으면 서버에 설정
      try {
        const resp = await fetch('/api/vault/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ vault_path: savedPath })
        });
        const data = await resp.json();
        if (data.ok) {
          currentVaultPath = data.vault_path;
        }
      } catch (err) {
        console.warn('Saved vault path restore failed:', err);
      }
    }
    
    // 서버에서 현재 경로 확인
    if (!currentVaultPath) {
      try {
        const resp = await fetch('/api/vault/config');
        const data = await resp.json();
        if (data.ok) {
          currentVaultPath = data.vault_path;
          localStorage.setItem(VAULT_PATH_KEY, currentVaultPath);
        }
      } catch (err) {
        console.error('Vault config load failed:', err);
      }
    }
    
    updateVaultPathDisplay();
    await loadTree();
  }
  
  function updateVaultPathDisplay() {
    if (currentVaultPath) {
      const shortPath = currentVaultPath.length > 40
        ? '...' + currentVaultPath.slice(-37)
        : currentVaultPath;
      vaultPathEl.textContent = `📁 ${shortPath}`;
      vaultPathEl.title = `Vault: ${currentVaultPath}\n클릭하여 경로 변경`;
    } else {
      vaultPathEl.textContent = '📁 미설정';
    }
  }

  // ─── 1. 트리 로드 ────────────────────────────────────────────
  async function loadTree() {
    try {
      const resp = await fetch('/api/vault/tree');
      const data = await resp.json();
      if (data.vault_path) {
        currentVaultPath = data.vault_path;
        updateVaultPathDisplay();
      }
      if (data.tree && data.tree.length > 0) {
        treeEl.innerHTML = renderTreeNodes(data.tree);
        bindTreeEvents();
      } else {
        treeEl.innerHTML = `
          <div style="text-align:center;padding:30px 16px;color:var(--text-muted);">
            <p style="font-size:13px;">문서가 없습니다.</p>
            <p style="font-size:11px;">"+" 버튼으로 첫 문서를 생성하세요.</p>
          </div>`;
      }
    } catch (err) {
      treeEl.innerHTML = `
        <div style="text-align:center;padding:30px 16px;color:#ef4444;font-size:12px;">
          Vault 로드 실패: ${err.message}
        </div>`;
    }
  }

  // ─── 2. 트리 이벤트 바인딩 ───────────────────────────────────
  function bindTreeEvents() {
    treeEl.querySelectorAll('.tree-item.folder').forEach(folder => {
      folder.addEventListener('click', (e) => {
        e.stopPropagation();
        const node = folder.parentElement;
        const children = node.querySelector('.tree-children');
        if (!children) return;
        const isOpen = children.style.display !== 'none';
        children.style.display = isOpen ? 'none' : 'block';
        folder.querySelector('.tree-icon').textContent = isOpen ? '📁' : '📂';
      });
    });

    treeEl.querySelectorAll('.tree-item.file').forEach(file => {
      file.addEventListener('click', (e) => {
        e.stopPropagation();
        treeEl.querySelectorAll('.tree-item.file').forEach(f => f.classList.remove('selected'));
        file.classList.add('selected');
        loadNote(file.dataset.path);
      });
    });
  }

  // ─── 3. 노트 로드 ───────────────────────────────────────────
  async function loadNote(path) {
    currentPath = path;
    breadcrumb.textContent = path;
    bodyEl.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">로딩 중...</div>';

    try {
      const resp = await fetch(`/api/vault/read?path=${encodeURIComponent(path)}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      currentContent = data.content || '';
      currentMetadata = data.metadata || {};

      let metaHtml = '';
      if (Object.keys(currentMetadata).length > 0) {
        const tags = currentMetadata.tags || [];
        metaHtml = `
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--glass-border);">
            ${currentMetadata.title ? `<span style="font-weight:600;font-size:12px;color:var(--text-secondary);">📝 ${currentMetadata.title}</span>` : ''}
            ${currentMetadata.date ? `<span style="font-size:11px;color:var(--text-muted);margin-left:auto;">${currentMetadata.date}</span>` : ''}
          </div>
          ${tags.length > 0 ? `<div style="display:flex;gap:4px;margin-bottom:12px;">${tags.map(t => `<span class="status-badge" style="background:var(--accent-subtle);color:var(--accent-color);font-size:11px;">#${t}</span>`).join('')}</div>` : ''}
        `;
      }

      bodyEl.innerHTML = metaHtml + renderMarkdown(currentContent);
      editBtn.style.display = 'inline-flex';
      chatRefBtn.style.display = 'inline-flex';
      saveBtn.style.display = 'none';
      cancelBtn.style.display = 'none';
      isEditing = false;
    } catch (err) {
      bodyEl.innerHTML = `<div style="color:#ef4444;padding:20px;">문서 로드 실패: ${err.message}</div>`;
    }
  }

  // ─── 4. 편집 모드 ───────────────────────────────────────────
  editBtn.addEventListener('click', () => {
    if (!currentPath) return;
    isEditing = true;
    editBtn.style.display = 'none';
    chatRefBtn.style.display = 'none';
    saveBtn.style.display = 'inline-flex';
    cancelBtn.style.display = 'inline-flex';

    bodyEl.innerHTML = `
      <textarea id="wiki-editor" style="
        width:100%;height:100%;min-height:400px;
        background:rgba(0,0,0,0.2);border:1px solid var(--glass-border);
        color:var(--text-primary);font-family:var(--font-mono);font-size:13px;
        padding:16px;border-radius:8px;resize:none;outline:none;line-height:1.7;
        box-sizing:border-box;
      ">${currentContent}</textarea>
    `;
    container.querySelector('#wiki-editor').focus();
  });

  saveBtn.addEventListener('click', async () => {
    if (!currentPath) return;
    const editor = container.querySelector('#wiki-editor');
    if (!editor) return;
    const newContent = editor.value;
    saveBtn.textContent = '⏳ 저장 중...';
    saveBtn.disabled = true;
    try {
      const resp = await fetch('/api/vault/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: currentPath, content: newContent, metadata: currentMetadata })
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      currentContent = newContent;
      loadNote(currentPath);
    } catch (err) {
      alert('저장 실패: ' + err.message);
    } finally {
      saveBtn.textContent = '💾 저장';
      saveBtn.disabled = false;
    }
  });

  cancelBtn.addEventListener('click', () => { if (currentPath) loadNote(currentPath); });

  // ─── 5. AI 채팅 참조 ────────────────────────────────────────
  chatRefBtn.addEventListener('click', () => {
    if (!currentPath || !currentContent) return;
    const snippet = currentContent.length > 500 ? currentContent.substring(0, 500) + '...' : currentContent;

    // 전역 상태에 참조 정보 저장
    window.__wikiChatRef = {
      path: currentPath,
      content: currentContent,
      metadata: currentMetadata,
      refText: `[Wiki: ${currentPath}]\n\n${snippet}`
    };

    // 채팅 탭으로 전환
    const chatNav = document.querySelector('.nav-item[data-page="chat"]');
    if (chatNav) chatNav.click();

    setTimeout(() => {
      const chatInput = document.getElementById('chat-input');
      if (chatInput) {
        chatInput.value = `다음 Wiki 문서를 참고하여 답변해주세요:\n\n---\n📄 ${currentPath}\n${snippet}\n---\n\n질문: `;
        chatInput.focus();
        chatInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }, 300);
  });

  // ─── 6. 검색 ────────────────────────────────────────────────
  let searchTimeout = null;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    const q = searchInput.value.trim();
    if (!q) { loadTree(); return; }
    searchTimeout = setTimeout(async () => {
      try {
        const resp = await fetch(`/v1/notes/search?q=${encodeURIComponent(q)}`);
        const data = await resp.json();
        const results = [
          ...(data.keyword_results || []),
          ...(data.semantic_results || []).map(r => r.metadata?.source || r.id)
        ];
        const unique = [...new Set(results)];
        if (unique.length > 0) {
          treeEl.innerHTML = unique.map(p => `
            <div class="tree-item file" data-path="${p}" style="padding:8px 16px;">
              <span class="tree-icon">🔍</span>
              <span class="tree-name">${p}</span>
            </div>`).join('');
          bindTreeEvents();
        } else {
          treeEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);font-size:12px;">검색 결과 없음</div>';
        }
      } catch (err) {
        treeEl.innerHTML = `<div style="padding:16px;color:var(--text-muted);font-size:12px;">검색 실패</div>`;
      }
    }, 400);
  });

  // ─── 7. 폴더 변경 ──────────────────────────────────────────
  const openFolderModal = () => {
    const input = container.querySelector('#wiki-folder-input');
    const currentEl = container.querySelector('#wiki-folder-current');
    input.value = currentVaultPath || '';
    currentEl.textContent = currentVaultPath ? `현재: ${currentVaultPath}` : '';
    folderModal.style.display = 'flex';
    input.focus();
  };
  
  folderBtn.addEventListener('click', openFolderModal);
  vaultPathEl.addEventListener('click', openFolderModal);
  container.querySelector('#wiki-folder-close').addEventListener('click', () => { folderModal.style.display = 'none'; });
  container.querySelector('#wiki-folder-cancel').addEventListener('click', () => { folderModal.style.display = 'none'; });
  
  container.querySelector('#wiki-folder-confirm').addEventListener('click', async () => {
    const input = container.querySelector('#wiki-folder-input');
    const newPath = input.value.trim();
    if (!newPath) { alert('경로를 입력하세요.'); return; }
    
    const confirmBtn = container.querySelector('#wiki-folder-confirm');
    confirmBtn.textContent = '⏳ 적용 중...';
    confirmBtn.disabled = true;
    
    try {
      const resp = await fetch('/api/vault/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vault_path: newPath })
      });
      const data = await resp.json();
      if (data.ok) {
        currentVaultPath = data.vault_path;
        // localStorage에 저장 → Chat 페이지에서도 참조 가능
        localStorage.setItem(VAULT_PATH_KEY, currentVaultPath);
        updateVaultPathDisplay();
        folderModal.style.display = 'none';
        // 트리 재로드
        currentPath = null;
        bodyEl.innerHTML = `
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:12px;color:var(--text-muted);">
            <span style="font-size:48px;opacity:0.3;">📚</span>
            <p style="font-size:14px;">문서를 선택하세요.</p>
          </div>`;
        editBtn.style.display = 'none';
        chatRefBtn.style.display = 'none';
        await loadTree();
      } else {
        alert('경로 변경 실패: ' + (data.detail || data.message || 'Unknown error'));
      }
    } catch (err) {
      alert('서버 오류: ' + err.message);
    } finally {
      confirmBtn.textContent = '적용';
      confirmBtn.disabled = false;
    }
  });

  // ─── 8. 새 문서 생성 ────────────────────────────────────────
  newBtn.addEventListener('click', () => { newModal.style.display = 'flex'; });
  container.querySelector('#wiki-new-close').addEventListener('click', () => { newModal.style.display = 'none'; });
  container.querySelector('#wiki-new-cancel').addEventListener('click', () => { newModal.style.display = 'none'; });
  container.querySelector('#wiki-new-confirm').addEventListener('click', async () => {
    const path = container.querySelector('#wiki-new-path').value.trim();
    const title = container.querySelector('#wiki-new-title').value.trim();
    const tagsStr = container.querySelector('#wiki-new-tags').value.trim();
    if (!path) { alert('파일 경로를 입력하세요.'); return; }
    if (!path.endsWith('.md')) { alert('.md 확장자가 필요합니다.'); return; }

    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
    const metadata = {
      title: title || path.split('/').pop().replace('.md', ''),
      tags,
      date: new Date().toISOString().split('T')[0]
    };
    const content = `\n# ${metadata.title}\n\n여기에 내용을 작성하세요.\n`;
    try {
      const resp = await fetch('/api/vault/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content, metadata })
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      newModal.style.display = 'none';
      container.querySelector('#wiki-new-path').value = '';
      container.querySelector('#wiki-new-title').value = '';
      container.querySelector('#wiki-new-tags').value = '';
      await loadTree();
      loadNote(path);
    } catch (err) {
      alert('문서 생성 실패: ' + err.message);
    }
  });

  // ─── Init ────────────────────────────────────────────────────
  setTimeout(() => { initVaultPath(); }, 0);

  return container;
};
