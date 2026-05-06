export const AgentPage = {
  render: () => `
    <div class="page-container full-height-page">
      <div class="page-header" style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h2>에이전트 현황 <span>Agent Workspace</span></h2>
            <p class="page-subtitle">에이전트가 백그라운드에서 진행 중인 작업과 플랜을 모니터링합니다.</p>
          </div>
          <div>
            <button id="refresh-kanban-btn" class="glass-btn primary" style="gap:8px;"><span>🔄</span> 새로고침</button>
          </div>
        </div>
      </div>

      <div class="kanban-board" id="agent-kanban-board">
        <div style="color:var(--text-secondary); text-align:center; width:100%; margin-top:50px;">
          <span class="spinner-mini"></span> 에이전트 작업 현황 로딩 중...
        </div>
      </div>
    </div>
  `,
  init: () => {
    const board = document.getElementById('agent-kanban-board');
    const refreshBtn = document.getElementById('refresh-kanban-btn');

    const renderCard = (task) => `
      <div class="kanban-card glass-panel ${task.status === 'completed' ? 'completed' : (task.status === 'in_progress' ? 'active' : '')}">
        <div class="card-labels">
          <span class="label ${task.priority === 'high' ? 'bug' : 'feature'}">${task.type || 'Task'}</span>
        </div>
        <h4>${escapeHTML(task.title || 'Untitled Task')}</h4>
        <p>${escapeHTML(task.description || '')}</p>
        <div class="card-meta" style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            ${task.status === 'in_progress' ? '<span class="spinner-mini"></span>' : (task.status === 'completed' ? '✅' : '🤖')}
            <span>${task.status === 'completed' ? '완료' : (task.status === 'in_progress' ? '실행 중...' : '대기 중')}</span>
          </div>
          ${(task.status === 'in_progress' || task.status === 'todo') ? `<button class="glass-btn small cancel-task-btn" data-id="${task.id}" style="color: #ff4444; border-color: rgba(255,68,68,0.3); padding: 2px 8px; font-size: 11px;">${task.status === 'todo' ? '🛑 취소' : '🛑 중단'}</button>` : ''}
        </div>
        ${task.status === 'in_progress' ? `
        <div class="progress-bar-wrap">
          <div class="progress-bar" style="width: 50%; animation: pulse 2s infinite;"></div>
        </div>` : ''}
      </div>
    `;

    const fetchTasks = () => {
      fetch('/api/kanban/tasks')
        .then(res => res.json())
        .then(data => {
          let tasks = data.data || [];

          const todo = tasks.filter(t => t.status === 'todo');
          const inprog = tasks.filter(t => t.status === 'in_progress');
          const done = tasks.filter(t => t.status === 'completed');

          const newHtml = `
            <div class="kanban-column">
              <div class="kanban-header"><h3>할 일 (To Do)</h3><span class="count-badge">${todo.length}</span></div>
              <div class="kanban-cards">${todo.map(renderCard).join('')}</div>
            </div>
            <div class="kanban-column active-column">
              <div class="kanban-header"><h3>진행 중 (In Progress)</h3><span class="count-badge">${inprog.length}</span></div>
              <div class="kanban-cards">${inprog.map(renderCard).join('')}</div>
            </div>
            <div class="kanban-column">
              <div class="kanban-header"><h3>완료 (Done)</h3><span class="count-badge">${done.length}</span></div>
              <div class="kanban-cards">${done.map(renderCard).join('')}</div>
            </div>
          `;

          if (board.innerHTML !== newHtml) {
            board.innerHTML = newHtml;
            // 강제 중단/취소 버튼 이벤트 바인딩
            board.querySelectorAll('.cancel-task-btn').forEach(btn => {
              btn.addEventListener('click', async (e) => {
                const taskId = e.target.getAttribute('data-id');
                const originalText = e.target.textContent;
                e.target.disabled = true;
                e.target.textContent = '처리 중...';

                try {
                  const res = await fetch(`/api/kanban/tasks/${taskId}/cancel`, { method: 'POST' });
                  if (!res.ok) throw new Error('Task cancellation failed');
                  fetchTasks();
                } catch (err) {
                  alert('처리 실패: ' + err.message);
                  e.target.disabled = false;
                  e.target.textContent = originalText;
                }
              });
            });
          }
        })
        .catch(err => {
          if (!board.innerHTML.includes('error-state')) {
            board.innerHTML = `<div class="error-state">작업 현황을 불러올 수 없습니다: ${err.message}</div>`;
          }
        });
    };

    fetchTasks();
    refreshBtn.addEventListener('click', fetchTasks);

    // 실시간 폴링 (DOM 트리에 보드가 존재할 때만 실행)
    if (window.__agentFetchInterval) clearInterval(window.__agentFetchInterval);
    window.__agentFetchInterval = setInterval(() => {
      if (document.getElementById('agent-kanban-board')) {
        fetchTasks();
      } else {
        clearInterval(window.__agentFetchInterval);
      }
    }, 2000);
  }
};

function escapeHTML(str) {
  return String(str).replace(/[&<>'"]/g,
    tag => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[tag] || tag)
  );
}
