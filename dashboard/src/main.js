/**
 * Antigravity-K Dashboard — Main Entry
 * =====================================
 * SPA 라우팅 + 페이지 렌더링 + WebSocket 연결
 */

import { ChatPage } from './pages/chat.js';
import { WikiPage } from './pages/wiki.js';
import { AgentPage } from './pages/agent.js';
import { SettingsPage } from './pages/settings.js';

import { initTerminal } from './terminal.js';

// ─── 상태 관리 ─────────────────────────────────────────────────────
const state = {
  currentPage: 'chat',
  backendStatus: { healthy: false, backends: {} },
  chatHistory: [],
};

// ─── API 클라이언트 ────────────────────────────────────────────────
const API_BASE = '/v1';
const BACKEND_API = '/api';

export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  try {
    const resp = await fetch(url, config);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.error(`API Error (${endpoint}):`, err);
    throw err;
  }
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
    // 1. 기존 LLM 상태 (v1/health)
    const data = await apiRequest('/health');
    state.backendStatus = data;

    if (data.status === 'ok') {
      statusDot.className = 'status-dot online';
      if (data.backends && Object.keys(data.backends).length > 0) {
        const activeCount = Object.keys(data.backends).length;
        statusText.textContent = `${activeCount}개 엔진 활성`;
      } else {
        statusText.textContent = `엔진 활성`;
      }
    } else {
      statusDot.className = 'status-dot offline';
      statusText.textContent = '추론 엔진 없음';
    }

    // 2. 서버 메트릭 상태 (/api/system/status)
    const sysResp = await fetch('/api/system/status');
    const sysData = await sysResp.json();
    if (sysData.ok) {
      metricsDiv.style.display = 'block';
      memSpan.textContent = sysData.memory_mb;
      cpuSpan.textContent = sysData.cpu_percent;
    }
  } catch (err) {
    console.error('System check failed:', err);
    statusDot.className = 'status-dot offline';
    statusText.textContent = '연결 실패';
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

  // 창 비율 조절 (Split.js)
  if (typeof Split !== 'undefined') {
    let sidebarSizes = [8, 92];
    try {
      const stored = localStorage.getItem('ide_sidebar_sizes_v2');
      if (stored) {
        sidebarSizes = JSON.parse(stored);
      }
    } catch(e) {}

    const sidebarSplit = Split(['#sidebar', '#right-container'], {
      sizes: sidebarSizes,
      minSize: [120, 400],
      gutterSize: 6,
      cursor: 'col-resize',
      onDragEnd: () => {
        localStorage.setItem('ide_sidebar_sizes_v2', JSON.stringify(sidebarSplit.getSizes()));
      }
    });
  }

  // 10초마다 시스템 상태 갱신 (더 빈번하게)
  setInterval(checkSystemStatus, 10000);
}

// DOM 로드 후 초기화
document.addEventListener('DOMContentLoaded', init);
