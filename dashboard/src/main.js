/**
 * Antigravity-K Dashboard — Main Entry
 * =====================================
 * SPA 라우팅 + 페이지 렌더링 + WebSocket 연결
 */

import { ChatPage } from './pages/chat.js';
import { WikiPage } from './pages/wiki.js';
import { AgentPage } from './pages/agent.js';
import { SettingsPage } from './pages/settings.js';
import { SkillsPage } from './pages/skills.js';

import { initTerminal } from './terminal.js';
import './command_palette.js';

// ─── 상태 관리 ─────────────────────────────────────────────────────
const state = {
  currentPage: 'chat',
  backendStatus: { healthy: false, backends: {} },
  chatHistory: [],
};

// ─── 프로젝트 관리 ────────────────────────────────────────────────
const PROJECTS_KEY = 'agk_projects';
const ACTIVE_PROJECT_KEY = 'agk_active_project';

function getProjects() {
  return JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
}

function saveProjects(projects) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
}

function getActiveProject() {
  return localStorage.getItem(ACTIVE_PROJECT_KEY) || null;
}

function setActiveProject(path) {
  localStorage.setItem(ACTIVE_PROJECT_KEY, path);
}

async function switchToProject(path) {
  try {
    const res = await fetch('/api/fs/workspace', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (data.ok) {
      setActiveProject(path);
      updateProjectSelector();
      // 페이지 새로고침하여 파일 트리/채팅/Wiki 모두 갱신
      if (window.showToast) window.showToast('프로젝트 전환: ' + path.split('/').pop(), 'success');
      setTimeout(() => location.reload(), 800);
    } else {
      alert('프로젝트 전환 실패: ' + (data.detail || '알 수 없음'));
    }
  } catch (err) {
    alert('서버 오류: ' + err.message);
  }
}

function updateProjectSelector() {
  const nameEl = document.getElementById('project-name');
  const dropdown = document.getElementById('project-dropdown');
  if (!nameEl || !dropdown) return;

  const projects = getProjects();
  const active = getActiveProject();

  // 현재 활성 프로젝트 이름 표시
  if (active) {
    nameEl.textContent = active.split('/').pop();
    nameEl.title = active;
  } else {
    nameEl.textContent = '기본 프로젝트';
  }

  // 드롭다운 구성
  let html = '';
  for (const p of projects) {
    const isActive = p.path === active;
    html += `
      <div class="project-item" data-path="${p.path}" style="
        display:flex; align-items:center; gap:8px;
        padding:8px 10px; border-radius:6px; cursor:pointer;
        font-size:12px; transition:background 0.15s ease;
        ${isActive ? 'background:rgba(124,106,239,0.12);' : ''}
      " onmouseover="this.style.background='rgba(255,255,255,0.06)';"
         onmouseout="this.style.background='${isActive ? 'rgba(124,106,239,0.12)' : 'transparent'}';">
        <span style="font-size:14px;">📁</span>
        <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${p.name}</span>
        ${isActive ? '<span style="color:#10b981; font-size:14px;">●</span>' : ''}
        <button class="project-remove" data-path="${p.path}" style="
          background:none; border:none; color:#565f89; cursor:pointer;
          font-size:14px; padding:0 4px; opacity:0.5;
        " onmouseover="this.style.opacity='1';this.style.color='#ef4444';"
           onmouseout="this.style.opacity='0.5';this.style.color='#565f89';">✕</button>
      </div>
    `;
  }
  html += `
    <div id="project-add-btn" style="
      display:flex; align-items:center; gap:8px;
      padding:8px 10px; border-radius:6px; cursor:pointer;
      font-size:12px; color:var(--text-secondary,#a9b1d6);
      border-top:1px solid rgba(255,255,255,0.05); margin-top:4px;
    " onmouseover="this.style.background='rgba(124,106,239,0.08)';"
       onmouseout="this.style.background='transparent';">
      <span style="font-size:14px;">➕</span> 프로젝트 추가
    </div>
  `;
  dropdown.innerHTML = html;

  // 프로젝트 항목 클릭
  dropdown.querySelectorAll('.project-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.classList.contains('project-remove')) return;
      const path = item.dataset.path;
      switchToProject(path);
      dropdown.style.display = 'none';
    });
  });

  // 프로젝트 제거
  dropdown.querySelectorAll('.project-remove').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const path = btn.dataset.path;
      const projects = getProjects().filter(p => p.path !== path);
      saveProjects(projects);
      updateProjectSelector();
    });
  });

  // 프로젝트 추가 — 폴더 브라우저 모달 사용
  const addBtn = dropdown.querySelector('#project-add-btn');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      dropdown.style.display = 'none';
      openFolderBrowser();
    });
  }
}

// ─── 글로벌 폴더 브라우저 ──────────────────────────────────────

let _gfbCurrentPath = '/';
let _gfbOnSelect = null; // 콜백

async function browseFolder(path) {
  _gfbCurrentPath = path;
  const listEl = document.getElementById('gfb-list');
  const pathEl = document.getElementById('gfb-path');
  if (!listEl) return;

  pathEl.textContent = path;
  listEl.innerHTML = '<div style="padding:20px; text-align:center; color:var(--text-muted);">로딩 중...</div>';

  try {
    const res = await fetch('/api/fs/browse?dir=' + encodeURIComponent(path));
    const data = await res.json();
    if (!data.ok) { listEl.innerHTML = '<div style="padding:16px; color:#ef4444;">폴더를 읽을 수 없습니다.</div>'; return; }

    let html = '';
    const items = data.items || [];
    if (items.length === 0) {
      html = '<div style="padding:20px; text-align:center; color:var(--text-muted); font-size:13px;">하위 폴더가 없습니다.</div>';
    } else {
      for (const item of items) {
        if (!item.is_dir) continue;
        html += `
          <div class="gfb-item" data-path="${item.path}" style="
            display:flex; align-items:center; gap:8px;
            padding:8px 14px; cursor:pointer; font-size:13px;
            color:var(--text-secondary); transition:all 0.15s ease;
            border-radius:6px; margin:0 6px;
          " onmouseover="this.style.background='rgba(124,106,239,0.1)'; this.style.color='var(--text-primary,#c0caf5)';"
             onmouseout="this.style.background='transparent'; this.style.color='var(--text-secondary,#a9b1d6)';">
            <span style="font-size:16px;">📁</span>
            <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${item.name}</span>
          </div>
        `;
      }
    }
    listEl.innerHTML = html;

    // 폴더 더블클릭 시 진입, 클릭 시 선택
    listEl.querySelectorAll('.gfb-item').forEach(item => {
      let clickTimer = null;
      item.addEventListener('click', () => {
        if (clickTimer) {
          clearTimeout(clickTimer);
          clickTimer = null;
          // 더블클릭 — 진입
          browseFolder(item.dataset.path);
        } else {
          clickTimer = setTimeout(() => {
            clickTimer = null;
            // 단일 클릭 — 선택 하이라이트
            listEl.querySelectorAll('.gfb-item').forEach(i => i.style.background = 'transparent');
            item.style.background = 'rgba(124,106,239,0.12)';
            _gfbCurrentPath = item.dataset.path;
            pathEl.textContent = item.dataset.path;
          }, 200);
        }
      });
    });

    // 상위 폴더 버튼
    const upBtn = document.getElementById('gfb-up');
    if (upBtn) {
      upBtn.onclick = () => {
        const parent = data.parent;
        if (parent) browseFolder(parent);
      };
    }
  } catch (err) {
    listEl.innerHTML = '<div style="padding:16px; color:#ef4444;">오류: ' + err.message + '</div>';
  }
}

function openFolderBrowser(onSelect) {
  _gfbOnSelect = onSelect || null;
  const modal = document.getElementById('global-folder-browser');
  if (!modal) return;

  // 시작 경로: 홈 디렉토리
  _gfbCurrentPath = '/';
  browseFolder('/');
  modal.style.display = 'flex';

  // 닫기 버튼
  document.getElementById('gfb-close').onclick = () => { modal.style.display = 'none'; };
  document.getElementById('gfb-cancel').onclick = () => { modal.style.display = 'none'; };

  // 확인 버튼 — 현재 경로 선택
  document.getElementById('gfb-confirm').onclick = () => {
    modal.style.display = 'none';
    const selectedPath = document.getElementById('gfb-path').textContent;
    if (_gfbOnSelect) {
      _gfbOnSelect(selectedPath);
    } else {
      // 기본 동작: 프로젝트로 추가
      addProjectFromPath(selectedPath);
    }
  };
}

function addProjectFromPath(path) {
  const name = path.split('/').pop() || 'Unnamed';
  const projects = getProjects();
  if (!projects.find(p => p.path === path)) {
    projects.push({ name, path });
    saveProjects(projects);
  }
  updateProjectSelector();
  switchToProject(path);
}

// 프로젝트 셀렉터 초기화 (DOM 로드 후)
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    const selector = document.getElementById('project-selector');
    const dropdown = document.getElementById('project-dropdown');
    if (!selector || !dropdown) return;

    // 첫 로드 시 현재 workspace를 기본 프로젝트로 등록
    fetch('/api/fs/workspace')
      .then(r => r.json())
      .then(data => {
        if (data.ok && data.workspace) {
          const ws = data.workspace;
          const name = ws.split('/').pop() || 'Root';
          const projects = getProjects();
          if (!projects.find(p => p.path === ws)) {
            projects.unshift({ name, path: ws });
            saveProjects(projects);
          }
          if (!getActiveProject()) setActiveProject(ws);
        }
        updateProjectSelector();
      })
      .catch(() => updateProjectSelector());

    // 드롭다운 토글
    selector.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    });

    // 외부 클릭 시 닫기
    document.addEventListener('click', () => {
      dropdown.style.display = 'none';
    });
  }, 500);
});

// ─── API 클라이언트 ────────────────────────────────────────────────
const API_BASE = '/v1';
const BACKEND_API = '/api';

function installConsoleNoiseFilter() {
  const originalWarn = console.warn.bind(console);
  console.warn = (...args) => {
    const message = args.map(arg => String(arg)).join(' ');
    if (message.includes("Duplicate definition of module 'vs/editor/editor.main'")) {
      return;
    }
    originalWarn(...args);
  };
}

installConsoleNoiseFilter();

export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const { suppressLog = false, ...requestOptions } = options;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...requestOptions,
  };

  try {
    const resp = await fetch(url, config);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (err) {
    if (!suppressLog) {
      console.error(`API Error (${endpoint}):`, err);
    }
    throw err;
  }
}

// ─── PIN Auth Interceptor ──────────────────────────────────────────
const originalFetch = window.fetch;
window.fetch = async function(...args) {
  let [resource, config] = args;
  const requestUrl = typeof resource === 'string' ? resource : resource?.url || '';
  const skipPinModal = Boolean(config?.skipPinModal);
  if (config && Object.prototype.hasOwnProperty.call(config, 'skipPinModal')) {
    config = { ...config };
    delete config.skipPinModal;
  }

  const pin = localStorage.getItem('ag_access_pin');
  if (pin) {
    config = config || {};
    config.headers = new Headers(config.headers || {});
    // FormData 등 기존 Content-Type을 보존하기 위해 단순 추가
    config.headers.set('X-Access-Pin', pin);
  }

  const response = await originalFetch(resource, config);

  const isBackgroundStatusCheck = requestUrl.includes('/api/system/status');
  if (response.status === 401 && !skipPinModal && !isBackgroundStatusCheck) {
    showPinModal();
  }
  return response;
};

function showPinModal() {
  if (document.getElementById('pin-auth-modal')) return;

  const modal = document.createElement('div');
  modal.id = 'pin-auth-modal';
  modal.className = 'modal-overlay open';
  modal.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.85);backdrop-filter:blur(10px);z-index:99999;display:flex;align-items:center;justify-content:center;flex-direction:column;';
  modal.innerHTML = `
    <div class="glass-panel" style="padding: 32px; border-radius: 16px; text-align: center; max-width: 300px; width: 90%;">
      <h2 style="margin-top:0;">🔒 시스템 잠금</h2>
      <p style="color:var(--text-secondary); font-size:13px; margin-bottom: 24px;">외부 접속 보안을 위해 PIN 번호를 입력하세요.</p>
      <input type="password" id="pin-input" placeholder="PIN 입력" style="width:100%; padding: 12px; border-radius:8px; border:1px solid var(--glass-border); background:rgba(0,0,0,0.5); color:#fff; text-align:center; font-size: 20px; letter-spacing: 4px; box-sizing: border-box; margin-bottom:16px;" autofocus>
      <button id="pin-submit-btn" class="glow-btn" style="width:100%; padding: 12px; border-radius: 8px; font-size: 15px; font-weight:bold;">잠금 해제</button>
      <div id="pin-error-msg" style="color:#ff6b6b; font-size:12px; margin-top:12px; display:none;">PIN 번호가 올바르지 않습니다.</div>
    </div>
  `;
  document.body.appendChild(modal);

  document.getElementById('pin-submit-btn').addEventListener('click', async () => {
    const pin = document.getElementById('pin-input').value;
    localStorage.setItem('ag_access_pin', pin);
    // SameSite=Strict prevents CSRF; Secure added when on HTTPS.
    const isHttps = window.location.protocol === 'https:';
    document.cookie = "ag_access_pin=" + pin + "; path=/; max-age=31536000; SameSite=Strict" + (isHttps ? "; Secure" : "");

    try {
      const res = await originalFetch('/api/session/info', {
        headers: { 'X-Access-Pin': pin }
      });
      if (res.ok) {
        modal.remove();
        window.location.reload();
      } else {
        document.getElementById('pin-error-msg').style.display = 'block';
      }
    } catch (e) {
      document.getElementById('pin-error-msg').style.display = 'block';
    }
  });

  document.getElementById('pin-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') document.getElementById('pin-submit-btn').click();
  });
}


// ─── Global UI Utils ───────────────────────────────────────────────
window.showToast = function(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
};
// ─── 네비게이션 ────────────────────────────────────────────────────
function setupNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const page = item.dataset.page;
      navigateTo(page);
    });
  });
}

function navigateTo(page) {
  state.currentPage = page;

  // Active 상태 업데이트
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.page === page);
  });

  // 페이지 렌더링
  renderPage(page);
}

const pageContainers = {};

function renderPage(page) {
  const main = document.getElementById('main-content');

  // 모든 컨테이너 숨기기
  Object.values(pageContainers).forEach(container => {
    container.style.display = 'none';
  });

  // 컨테이너가 없으면 생성 및 렌더링
  if (!pageContainers[page]) {
    const container = document.createElement('div');
    container.id = `page-${page}`;
    container.style.width = '100%';
    container.style.height = '100%';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';

    switch (page) {
      case 'chat':
        container.innerHTML = ChatPage.render();
        main.appendChild(container);
        ChatPage.init();
        break;
      case 'rag':
      case 'wiki':
        container.appendChild(WikiPage());
        main.appendChild(container);
        break;
      case 'agent':
        container.innerHTML = AgentPage.render();
        main.appendChild(container);
        AgentPage.init();
        break;
      case 'skills':
        container.innerHTML = SkillsPage.render();
        main.appendChild(container);
        SkillsPage.init();
        break;
      case 'settings':
        container.innerHTML = SettingsPage.render();
        main.appendChild(container);
        SettingsPage.init();
        break;
      default:
        container.innerHTML = renderPlaceholder('404', '🔍', '페이지를 찾을 수 없습니다.');
        main.appendChild(container);
    }
    pageContainers[page] = container;
  }

  // 현재 페이지 컨테이너만 보이기
  pageContainers[page].style.display = 'flex';
}

function renderPlaceholder(title, icon, description) {
  return `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:16px;color:var(--text-muted);">
      <span style="font-size:64px;opacity:0.5;">${icon}</span>
      <h2 style="font-size:24px;font-weight:600;color:var(--text-secondary);">${title}</h2>
      <p style="font-size:14px;max-width:400px;text-align:center;line-height:1.6;">${description}</p>
    </div>
  `;
}

// ─── 시스템 상태 체크 및 재시작 ──────────────────────────────────────────────
async function checkSystemStatus() {
  const statusDot = document.querySelector('.status-dot');
  const statusText = document.querySelector('.status-text');

  const metricsDiv = document.getElementById('system-metrics');
  const memSpan = document.getElementById('sys-mem');
  const cpuSpan = document.getElementById('sys-cpu');

  try {
    // 1. 기존 LLM 상태 (v1/health). Polling failures update UI state without console errors.
    const data = await apiRequest('/health', { suppressLog: true });
    state.backendStatus = data;

    if (data.status === 'ok') {
      statusDot.className = 'status-dot online';
      if (data.backends && Object.keys(data.backends).length > 0) {
        const activeCount = Object.keys(data.backends).length;
        statusText.textContent = `${activeCount}개 엔진 활성`;
      } else {
        statusText.textContent = `엔진 활성`;
      }

      // RAG / CoV 시스템 상태 업데이트
      const agentMetricsDiv = document.getElementById('system-agent-metrics');
      if (agentMetricsDiv) {
        agentMetricsDiv.style.display = 'block';
        document.getElementById('sys-rag').textContent = data.rag_index_files || '0';
        document.getElementById('sys-cov').textContent = data.cov_active ? 'On' : 'Off';
        if (data.cov_active) {
            document.getElementById('sys-cov').style.color = '#10b981'; // green
        }
      }

      // P2-1: 프로바이더 상태 패널 업데이트
      updateProviderStatusPanel(data);
      // P2-2: 비용 게이지 업데이트
      updateCostGauge(data);
    } else {
      statusDot.className = 'status-dot offline';
      statusText.textContent = '추론 엔진 없음';
      const agentMetricsDiv = document.getElementById('system-agent-metrics');
      if (agentMetricsDiv) agentMetricsDiv.style.display = 'none';
    }
  } catch (err) {
    statusDot.className = 'status-dot offline';
    statusText.textContent = '연결 실패';
    const agentMetricsDiv = document.getElementById('system-agent-metrics');
    if (agentMetricsDiv) agentMetricsDiv.style.display = 'none';
  }

  try {
    const sysResp = await fetch('/api/system/status', { skipPinModal: true });
    if (sysResp.status === 401) {
      metricsDiv.style.display = 'none';
      return;
    }
    if (!sysResp.ok) {
      metricsDiv.style.display = 'none';
      return;
    }
    const sysData = await sysResp.json();
    if (sysData.ok) {
      metricsDiv.style.display = 'block';
      memSpan.textContent = sysData.memory_mb; // Now actually represents percentage
      cpuSpan.textContent = sysData.cpu_percent;
      const tokensSpan = document.getElementById('sys-tokens');
      if (tokensSpan && sysData.total_tokens !== undefined) {
          tokensSpan.textContent = sysData.total_tokens.toLocaleString();
      }
    } else {
      metricsDiv.style.display = 'none';
    }
  } catch (err) {
    metricsDiv.style.display = 'none';
  }
}

function initServerRestart() {
  const restartBtn = document.getElementById('restart-server-btn');
  if (!restartBtn) return;

  restartBtn.addEventListener('click', async () => {
    const confirmRestart = confirm("정말로 서버를 재시작하시겠습니까?");
    if (!confirmRestart) return;

    try {
      restartBtn.disabled = true;
      restartBtn.innerHTML = '⏳ 재시작 중...';
      await fetch('/api/system/restart', { method: 'POST' });

      // 모달 표시 (또는 alert)
      const overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:10000;display:flex;align-items:center;justify-content:center;flex-direction:column;color:white;';
      overlay.innerHTML = `<h2>🚀 서버 재시작 중...</h2><p>잠시 후 페이지가 새로고침됩니다.</p>`;
      document.body.appendChild(overlay);

      // 3초 후 페이지 새로고침
      setTimeout(() => {
        window.location.reload();
      }, 3000);

    } catch(err) {
      alert("재시작 실패: " + err.message);
      restartBtn.disabled = false;
      restartBtn.innerHTML = '🔄 서버 재시작';
    }
  });
}

// ─── 안티그래비티 이스터에그 (Google Antigravity) ───────────────────
function initAntigravity() {
  const trigger = document.getElementById('antigravity-trigger');
  if (!trigger) return;

  let isGravityOn = false;

  trigger.addEventListener('click', () => {
    if (isGravityOn) return; // 한 번만 실행
    isGravityOn = true;

    // Matter.js 엔진 설정
    const Engine = Matter.Engine,
          Render = Matter.Render,
          Runner = Matter.Runner,
          Bodies = Matter.Bodies,
          Composite = Matter.Composite;

    const engine = Engine.create();
    // 안티그래비티: 위로 떠오르거나(무중력) 약간 아래로 떨어지게 설정
    engine.world.gravity.y = -0.5; // 안티그래비티 (위로 올라감)

    const render = Render.create({
      element: document.body,
      engine: engine,
      options: {
        width: window.innerWidth,
        height: window.innerHeight,
        wireframes: false,
        background: 'transparent'
      }
    });

    render.canvas.style.position = 'fixed';
    render.canvas.style.top = '0';
    render.canvas.style.left = '0';
    render.canvas.style.pointerEvents = 'none';
    render.canvas.style.zIndex = '9999';

    // 화면 테두리 (벽)
    const bounds = {
      top: Bodies.rectangle(window.innerWidth / 2, -50, window.innerWidth, 100, { isStatic: true }),
      bottom: Bodies.rectangle(window.innerWidth / 2, window.innerHeight + 50, window.innerWidth, 100, { isStatic: true }),
      left: Bodies.rectangle(-50, window.innerHeight / 2, 100, window.innerHeight, { isStatic: true }),
      right: Bodies.rectangle(window.innerWidth + 50, window.innerHeight / 2, 100, window.innerHeight, { isStatic: true })
    };
    Composite.add(engine.world, [bounds.top, bounds.bottom, bounds.left, bounds.right]);

    // DOM 요소들을 물리 객체로 변환
    const elements = document.querySelectorAll('.nav-item, .stat-card, .model-card, .btn-primary, .search-input-group, .wiki-card, .message-bubble, .page-header');

    elements.forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      const body = Bodies.rectangle(
        rect.left + rect.width / 2,
        rect.top + rect.height / 2,
        rect.width,
        rect.height,
        {
          restitution: 0.8,
          friction: 0.05,
          render: { visible: false }
        }
      );

      // DOM과 물리엔진 동기화
      const updateDOM = () => {
        el.style.position = 'fixed';
        el.style.left = `${body.position.x - rect.width / 2}px`;
        el.style.top = `${body.position.y - rect.height / 2}px`;
        el.style.transform = `rotate(${body.angle}rad)`;
        el.style.zIndex = '1000';
        el.style.margin = '0';
        requestAnimationFrame(updateDOM);
      };

      Composite.add(engine.world, body);
      requestAnimationFrame(updateDOM);

      // 약간의 랜덤 힘을 가해서 흩어지게 만듦
      Matter.Body.setVelocity(body, {
        x: (Math.random() - 0.5) * 10,
        y: (Math.random() - 0.5) * 10
      });
    });

    Render.run(render);
    const runner = Runner.create();
    Runner.run(runner, engine);

    // 마우스 상호작용 추가
    const mouse = Matter.Mouse.create(document.body);
    const mouseConstraint = Matter.MouseConstraint.create(engine, {
      mouse: mouse,
      constraint: {
        stiffness: 0.2,
        render: { visible: false }
      }
    });
    Composite.add(engine.world, mouseConstraint);

    // 캔버스가 마우스 이벤트를 받도록 허용
    render.canvas.style.pointerEvents = 'auto';
  });
}

// ─── 초기화 ────────────────────────────────────────────────────────
function init() {
  setupNavigation();
  renderPage('chat');
  checkSystemStatus();
  initServerRestart();
  initAntigravity();
  initTerminal();
  initModeTooltip();

  // 창 비율 조절 (Split.js)
  let sidebarSplit;
  let sidebarSizes = [8, 92];

  if (typeof Split !== 'undefined') {
    try {
      const stored = localStorage.getItem('ide_sidebar_sizes_v2');
      if (stored) {
        sidebarSizes = JSON.parse(stored);
      }
    } catch(e) {}

    sidebarSplit = Split(['#sidebar', '#right-container'], {
      sizes: sidebarSizes,
      minSize: [0, 400],
      gutterSize: 6,
      cursor: 'col-resize',
      onDragEnd: () => {
        localStorage.setItem('ide_sidebar_sizes_v2', JSON.stringify(sidebarSplit.getSizes()));
      }
    });
  }

  // Cmd+B / Ctrl+B: 전체 사이드바 토글
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      const sidebar = document.getElementById('sidebar');
      // Split.js가 추가한 gutter는 sidebar 바로 다음 형제 요소
      const gutter = sidebar.nextElementSibling;
      const rightContainer = document.getElementById('right-container');

      if (sidebar.style.display === 'none') {
        sidebar.style.display = 'flex';
        if (gutter && gutter.classList.contains('gutter')) gutter.style.display = 'block';
        if (sidebarSplit) sidebarSplit.setSizes(sidebarSizes);
      } else {
        if (sidebarSplit) sidebarSizes = sidebarSplit.getSizes();
        sidebar.style.display = 'none';
        if (gutter && gutter.classList.contains('gutter')) gutter.style.display = 'none';
        // 오른쪽 컨테이너를 100%로 강제 확장
        rightContainer.style.width = '100%';
      }

      // Monaco 에디터가 있으면 리사이즈 유도
      if (window.monaco && window.monaco.editor) {
        setTimeout(() => {
          const editors = window.monaco.editor.getEditors();
          editors.forEach(ed => ed.layout());
        }, 10);
      }
    }
  });

  // 10초마다 시스템 상태 갱신 (더 빈번하게)
  setInterval(checkSystemStatus, 10000);

  // Phase 1 D7: WebSocket 연결 + 모드 인디케이터 초기화
  initModeIndicator();
  connectModeWebSocket();
}

// ─── 모드 인디케이터 ────────────────────────────────────────────────
// Phase 1 D7: 실행 모드(Plan/Build/Interactive) 표시 및 WebSocket 연동

const MODE_STYLES = {
  plan: {
    icon: '📋',
    label: 'PLAN',
    color: '#fbbf24',      // yellow/amber
    bg: 'rgba(251, 191, 36, 0.12)',
    border: '1px solid rgba(251, 191, 36, 0.3)',
    description: '읽기 전용 도구만 허용'
  },
  build: {
    icon: '🔨',
    label: 'BUILD',
    color: '#10b981',      // green/emerald
    bg: 'rgba(16, 185, 129, 0.12)',
    border: '1px solid rgba(16, 185, 129, 0.3)',
    description: '모든 도구 실행 허용'
  },
  interactive: {
    icon: '💬',
    label: 'INTERACTIVE',
    color: '#06b6d4',      // cyan
    bg: 'rgba(6, 182, 212, 0.12)',
    border: '1px solid rgba(6, 182, 212, 0.3)',
    description: '기본 대화형 모드'
  }
};

function initModeIndicator() {
  const indicator = document.getElementById('mode-indicator');
  if (!indicator) return;
  // 초기값: interactive (서버 상태 확인 후 업데이트)
  updateModeDisplay('interactive');

  // 클릭 시 모드 전환 드롭다운
  const modes = ['interactive', 'plan', 'build'];
  const currentDisplay = () => document.getElementById('mode-label')?.textContent?.toLowerCase() || 'interactive';
  let currentModeIdx = 0;

  indicator.addEventListener('click', async (e) => {
    e.stopPropagation();

    // 간단한 사이클: 클릭할 때마다 다음 모드로 전환
    currentModeIdx = (currentModeIdx + 1) % modes.length;
    const nextMode = modes[currentModeIdx];

    // 서버에 모드 전환 요청
    const pin = localStorage.getItem('ag_access_pin') || '0000';
    try {
      const res = await fetch('/api/system/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Pin': pin },
        body: JSON.stringify({ mode: nextMode, reason: '대시보드 클릭' }),
      });
      const data = await res.json();
      if (data.ok) {
        updateModeDisplay(nextMode);
        if (window.showToast) {
          const labels = { interactive: '💬 Interactive (대화형)', plan: '📋 Plan (계획)', build: '🔨 Build (실행)' };
          window.showToast('모드 전환: ' + (labels[nextMode] || nextMode), 'success');
        }
      } else {
        if (window.showToast) window.showToast('모드 전환 실패: ' + (data.error || ''), 'error');
        // 실패 시 인덱스 되돌리기
        currentModeIdx = (currentModeIdx - 1 + modes.length) % modes.length;
      }
    } catch (err) {
      if (window.showToast) window.showToast('서버 오류: ' + err.message, 'error');
      currentModeIdx = (currentModeIdx - 1 + modes.length) % modes.length;
    }
  });
}

function updateModeDisplay(mode) {
  const indicator = document.getElementById('mode-indicator');
  const iconEl = document.getElementById('mode-icon');
  const labelEl = document.getElementById('mode-label');
  const dotEl = document.getElementById('mode-dot');
  if (!indicator || !iconEl || !labelEl) return;

  const style = MODE_STYLES[mode] || MODE_STYLES.interactive;

  // Update content
  iconEl.textContent = style.icon;
  labelEl.textContent = style.label;

  // Update styling
  indicator.style.background = style.bg;
  indicator.style.borderColor = style.color;
  indicator.style.border = style.border;
  labelEl.style.color = style.color;

  // Update class for CSS transitions
  indicator.className = indicator.className.replace(/\b(plan|build|interactive)\b/g, '');
  indicator.classList.add(mode);

  // Title tooltip
  indicator.title = `${style.label} 모드 — ${style.description}`;

  // Dot color
  if (dotEl) {
    dotEl.style.background = style.color;
    dotEl.style.boxShadow = `0 0 6px ${style.color}`;
  }
}

function connectModeWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/v1/ws/events`;

  let ws = null;
  let reconnectTimer = null;
  let pingInterval = null;

  function connect() {
    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      console.warn('[ModeWS] Connection failed, retrying in 10s...');
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      console.log('[ModeWS] Connected to event stream');
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      // Send initial status request
      fetchCurrentMode();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'ModeChanged') {
          const newMode = msg.data?.to_mode;
          if (newMode && MODE_STYLES[newMode]) {
            updateModeDisplay(newMode);
            window.showToast(`🔄 모드 전환: ${newMode.toUpperCase()}`, 'info');
          }
        }
      } catch (e) {
        // Ignore parse errors
      }
    };

    ws.onclose = () => {
      console.log('[ModeWS] Disconnected');
      stopPing();
      scheduleReconnect();
    };

    ws.onerror = () => {
      console.warn('[ModeWS] Error');
      ws.close();
    };

    // Start periodic ping
    startPing();
  }

  function startPing() {
    stopPing();
    pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  function stopPing() {
    if (pingInterval) {
      clearInterval(pingInterval);
      pingInterval = null;
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 10000);
  }

  async function fetchCurrentMode() {
    try {
      const resp = await fetch('/api/system/mode', { skipPinModal: true });
      if (resp.ok) {
        const data = await resp.json();
        if (data.mode && MODE_STYLES[data.mode]) {
          updateModeDisplay(data.mode);
        }
      }
    } catch (e) {
      console.debug('[ModeWS] Could not fetch initial mode');
    }
  }

  connect();

  // Store reference for cleanup
  window.__modeWS = ws;
  window.__modeReconnectTimer = reconnectTimer;
  window.__modePingInterval = pingInterval;
}

// ─── Mode Indicator Enhanced (D16) ───────────────────────────────
// Phase 1 D16: 모드 인디케이터 호버 시 상세 히스토리 툴팁 표시

function initModeTooltip() {
  const indicator = document.getElementById('mode-indicator');
  if (!indicator) return;

  // 호버 시 모드 히스토리 fetch
  indicator.addEventListener('mouseenter', async () => {
    try {
      const res = await fetch('/api/system/mode/history', { skipPinModal: true });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.ok || !data.history?.length) return;

      // 최근 5개만 표시
      const recent = data.history.slice(-5).reverse();
      const lines = recent.map(h => {
        const time = h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : '';
        return `${time} ${h.from} → ${h.to}${h.reason ? ': ' + h.reason : ''}`;
      });
      indicator.title = `📋 최근 모드 전환 히스토리:\n${lines.join('\n')}`;
    } catch (e) {
      // Silent
    }
  });
}

// ═══ P2-1: 프로바이더 상태 패널 ═══
function updateProviderStatusPanel(healthData) {
  const panel = document.getElementById('provider-status-panel');
  if (!panel) return;

  // config.yaml의 providers 정보는 백엔드에서 직접 가져오기 어려우므로
  // healthData의 backends에서 활성 모델을 추출하여 표시
  const backends = healthData.backends || [];
  const activeModels = Array.isArray(backends) ? backends : Object.values(backends);

  // 알려진 프로바이더 목록 (정적)
  const knownProviders = [
    { name: 'Ollama', key: 'ollama', icon: '🏠' },
    { name: 'OpenRouter', key: 'openrouter', icon: '🌐' },
    { name: 'NIM', key: 'nim', icon: '🟢' },
    { name: 'OpenAI', key: 'openai', icon: '🔵' },
    { name: 'Gemini', key: 'gemini', icon: '✨' },
    { name: 'ZAI', key: 'zai', icon: '🧠' },
  ];

  // 활성 모델 이름에서 프로바이더 추론
  const activeProviders = new Set();
  activeModels.forEach(m => {
    const name = (m.name || m.model || '').toLowerCase();
    if (name.includes('ollama') || name.includes(':latest') || name.includes(':')) activeProviders.add('ollama');
    if (name.includes('openrouter') || name.includes('/') && !name.startsWith('gpt') && !name.startsWith('claude')) activeProviders.add('openrouter');
    if (name.startsWith('deepseek-ai/') || name.startsWith('meta/') || name.startsWith('nvidia/')) activeProviders.add('nim');
    if (name.startsWith('gpt') || name.startsWith('o3')) activeProviders.add('openai');
    if (name.startsWith('gemini')) activeProviders.add('gemini');
    if (name.startsWith('glm')) activeProviders.add('zai');
  });

  const badges = knownProviders.map(p => {
    const active = activeProviders.has(p.key);
    return `<span class="provider-badge ${active ? 'active' : 'inactive'}" title="${p.name}">
      <span class="dot"></span>${p.icon} ${p.name}
    </span>`;
  }).join('');

  panel.innerHTML = badges;
  panel.style.display = 'flex';
}

// ═══ P2-2: 비용 게이지 ═══
function updateCostGauge(healthData) {
  const gauge = document.getElementById('cost-gauge');
  const fill = document.getElementById('cost-bar-fill');
  const text = document.getElementById('cost-text');
  if (!gauge || !fill || !text) return;

  // healthData에서 비용 정보가 오면 표시 (향후 백엔드 확장 시)
  // 현재는 사용량 추적 데이터가 없으므로 숨김 유지
  if (healthData.daily_spend_usd !== undefined) {
    const spent = healthData.daily_spend_usd || 0;
    const budget = healthData.daily_budget_usd || 50;
    const pct = Math.min(100, (spent / budget) * 100);
    fill.style.width = pct + '%';
    text.textContent = `$${spent.toFixed(2)} / $${budget.toFixed(0)}`;
    gauge.style.display = 'flex';
  }
}

// DOM 로드 후 초기화
document.addEventListener('DOMContentLoaded', init);
