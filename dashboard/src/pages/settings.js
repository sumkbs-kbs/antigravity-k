export const SettingsPage = {
  render: () => `
    <div class="page-container" style="max-width: 800px;">
      <div class="page-header" style="margin-bottom: 24px;">
        <h2>시스템 설정 <span>Settings</span></h2>
        <p class="page-subtitle">엔진 및 하이브리드 LLM 라우팅 구성을 확인합니다. (읽기 전용)</p>
      </div>

      <div id="settings-container" style="display: flex; flex-direction: column; gap: 20px;">
        <div class="loading-state">설정 불러오는 중...</div>
      </div>
    </div>
  `,
  init: () => {
    const container = document.getElementById('settings-container');

    fetch('/api/settings')
      .then(res => res.json())
      .then(data => {
        if (!data || !data.settings) {
          container.innerHTML = '<div class="error-state">설정을 불러올 수 없습니다.</div>';
          return;
        }

        const cfg = data.settings;
        let html = '';

        // API Keys Card
        html += `
          <div class="glass-panel" style="padding: 24px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🔑</span> API 키 및 인증
            </h3>
            <div style="display: grid; grid-template-columns: 150px 1fr; gap: 12px; align-items: center; font-size: 14px;">
        `;
        if (cfg.api_keys) {
          for (const [key, val] of Object.entries(cfg.api_keys)) {
            html += `
              <div style="color: var(--text-secondary); font-weight: 500;">${key.toUpperCase()}</div>
              <div><input type="text" readonly class="glass-input" value="${val || '미설정'}" style="width: 100%; opacity: 0.7;"></div>
            `;
          }
        } else {
          html += `<div style="grid-column: span 2; color: var(--text-secondary);">설정된 API 키가 없습니다.</div>`;
        }
        html += `</div></div>`;

        // Router Settings Card
        html += `
          <div class="glass-panel" style="padding: 24px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🔀</span> 하이브리드 모델 라우터
            </h3>
            <div style="display: grid; grid-template-columns: 150px 1fr; gap: 12px; align-items: center; font-size: 14px;">
              <div style="color: var(--text-secondary); font-weight: 500;">기본 로컬 모델</div>
              <div><span class="status-badge" style="background: rgba(255,255,255,0.1);">${cfg.model?.name || '미설정'}</span></div>
              
              <div style="color: var(--text-secondary); font-weight: 500;">공급자 (Provider)</div>
              <div><span class="status-badge active">${cfg.model?.provider || 'ollama'}</span></div>
              
              <div style="color: var(--text-secondary); font-weight: 500;">임베딩 모델</div>
              <div><span class="status-badge" style="background: rgba(255,255,255,0.1);">${cfg.embedding?.model || '미설정'}</span></div>
            </div>
          </div>
        `;

        // Server Settings
        html += `
          <div class="glass-panel" style="padding: 24px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🖥</span> 서버 구성
            </h3>
            <div style="display: grid; grid-template-columns: 150px 1fr; gap: 12px; align-items: center; font-size: 14px;">
              <div style="color: var(--text-secondary); font-weight: 500;">호스트 (Host)</div>
              <div>${cfg.server?.host || '0.0.0.0'}</div>
              
              <div style="color: var(--text-secondary); font-weight: 500;">포트 (Port)</div>
              <div>${cfg.server?.port || '8000'}</div>
            </div>
          </div>
        `;

        container.innerHTML = html;
      })
      .catch(err => {
        container.innerHTML = `<div class="error-state">설정 파싱 중 오류 발생: ${err.message}</div>`;
      });
  }
};
