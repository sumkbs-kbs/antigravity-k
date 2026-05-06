export const LogsPage = {
  render: () => `
    <div class="page-container" style="max-width: 1200px; display: flex; flex-direction: column; height: 100%;">
      <div class="page-header" style="margin-bottom: 20px; flex-shrink: 0;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h2>감사 로그 <span>Audit Logs</span></h2>
            <p class="page-subtitle">에이전트의 모든 활동, API 호출, 샌드박스 실행 내역을 실시간으로 추적합니다.</p>
          </div>
          <button id="refresh-logs-btn" class="glass-btn primary" style="gap: 8px;">
            <span>🔄</span> 새로고침
          </button>
        </div>
      </div>

      <div class="glass-panel" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; background: #0d0d0d; font-family: 'JetBrains Mono', monospace;">
        <div style="padding: 12px 16px; background: rgba(255,255,255,0.05); border-bottom: 1px solid var(--glass-border); display: flex; gap: 16px; font-size: 13px;">
          <label style="display:flex; align-items:center; gap:6px;">
            <input type="checkbox" checked id="auto-scroll-toggle"> Auto-scroll
          </label>
        </div>
        <div id="logs-container" style="flex: 1; overflow-y: auto; padding: 16px; font-size: 13px; line-height: 1.5; color: #a9b7c6; word-break: break-all;">
          <div style="color: #666;">로그를 불러오는 중...</div>
        </div>
      </div>
    </div>
  `,
  init: () => {
    const container = document.getElementById('logs-container');
    const refreshBtn = document.getElementById('refresh-logs-btn');
    const autoScroll = document.getElementById('auto-scroll-toggle');

    const fetchLogs = () => {
      fetch('/api/logs?lines=200')
        .then(res => res.json())
        .then(data => {
          if (!data || !data.logs || data.logs.length === 0) {
            container.innerHTML = '<div style="color: #666;">기록된 로그가 없습니다.</div>';
            return;
          }
          container.innerHTML = data.logs.map(line => {
            // 간단한 로그 포맷팅 (에러는 빨간색, 인포는 파란색 등)
            let color = '#a9b7c6';
            if (line.includes('ERROR') || line.includes('Exception')) color = '#ff5555';
            else if (line.includes('WARNING')) color = '#ffb86c';
            else if (line.includes('INFO')) color = '#8be9fd';
            return `<div style="color: ${color}; white-space: pre-wrap;">${escapeHTML(line)}</div>`;
          }).join('');

          if (autoScroll.checked) {
            container.scrollTop = container.scrollHeight;
          }
        })
        .catch(err => {
          container.innerHTML = `<div style="color: #ff5555;">로그를 불러오는 중 오류가 발생했습니다: ${err.message}</div>`;
        });
    };

    fetchLogs();
    refreshBtn.addEventListener('click', fetchLogs);

    // 5초마다 자동 새로고침 (라우팅 변경 시 클리어)
    const interval = setInterval(() => {
      if (!document.getElementById('logs-container')) {
        clearInterval(interval);
        return;
      }
      fetchLogs();
    }, 5000);
  }
};

function escapeHTML(str) {
  return str.replace(/[&<>'"]/g,
    tag => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[tag])
  );
}
