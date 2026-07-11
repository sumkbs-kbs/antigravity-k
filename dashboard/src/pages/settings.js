export const SettingsPage = {
  render: () => `
    <div class="page-container" style="max-width: 800px;">
      <div class="page-header" style="margin-bottom: 24px;">
        <h2>시스템 설정 <span>Settings</span></h2>
        <p class="page-subtitle">API 키, 모델, 검색 엔진, 비용 제어를 설정합니다.</p>
      </div>
      <div id="settings-container" style="display: flex; flex-direction: column; gap: 20px;">
        <div class="loading-state">설정 불러오는 중...</div>
      </div>
    </div>
  `,
  init: () => {
    const container = document.getElementById('settings-container');

    // localStorage에서 저장된 설정 불러오기
    const savedSettings = JSON.parse(localStorage.getItem('agk_user_settings') || '{}');

    // 현재 .env에서 로드된 설정 조회 (표시용)
    fetch('/api/settings')
      .then(res => res.json())
      .then(data => {
        const cfg = data.settings || {};
        let html = '';

        // ═══ 1. API 키 설정 (편집 가능) ═══
        const providers = [
          { key: 'OPENROUTER_API_KEY', label: 'OpenRouter', icon: '🌐', hint: 'openrouter.ai/keys' },
          { key: 'NVIDIA_API_KEY', label: 'NVIDIA NIM (무료)', icon: '🟢', hint: 'build.nvidia.com' },
          { key: 'OPENAI_API_KEY', label: 'OpenAI', icon: '🔵', hint: 'platform.openai.com/api-keys' },
          { key: 'GEMINI_API_KEY', label: 'Google Gemini', icon: '✨', hint: 'aistudio.google.com/apikey' },
          { key: 'ZAI_API_KEY', label: 'ZAI / Zhipu GLM', icon: '🧠', hint: 'open.bigmodel.cn' },
          { key: 'ANTHROPIC_API_KEY', label: 'Anthropic Claude', icon: '🟣', hint: 'console.anthropic.com' },
        ];

        html += `
          <div class="glass-panel" style="padding: 24px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🔑</span> API 키 설정
            </h3>
            <p style="font-size:12px; color:var(--text-muted,#565f89); margin-bottom:16px;">
              사용할 프로바이더의 API 키를 입력하세요. 입력된 키는 서버 재시작 후 적용됩니다.
            </p>
            <div style="display: flex; flex-direction: column; gap: 14px;">
        `;

        providers.forEach(p => {
          const envValue = cfg.api_keys?.[p.key] || cfg.api_keys?.[p.key.toLowerCase()] || '';
          const savedValue = savedSettings[p.key] || '';
          const isSet = savedValue || envValue;
          const displayValue = savedValue || '';
          const statusBadge = isSet
            ? '<span style="color:#10b981; font-size:11px;">✓ 설정됨</span>'
            : '<span style="color:#565f89; font-size:11px;">⚪ 미설정</span>';

          html += `
            <div style="display:flex; align-items:center; gap:12px;">
              <div style="width:140px; flex-shrink:0;">
                <div style="font-size:13px; font-weight:500;">${p.icon} ${p.label}</div>
                <div style="font-size:10px; color:var(--text-muted,#565f89);">${p.hint}</div>
              </div>
              <input type="password" class="glass-input setting-input" data-key="${p.key}"
                placeholder="${isSet ? '•••••••• (재입력 시 덮어쓰기)' : 'API 키 입력'}"
                value="${displayValue}"
                style="flex:1; font-size:13px; font-family:'JetBrains Mono',monospace;">
              <div style="width:80px; text-align:right;">${statusBadge}</div>
            </div>
          `;
        });

        html += `</div></div>`;

        // ═══ 2. 기본 모델 선택 ═══
        const defaultModel = savedSettings.default_model || cfg.model?.name || '';
        html += `
          <div class="glass-panel" style="padding: 24px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🤖</span> 기본 모델
            </h3>
            <div style="display:flex; align-items:center; gap:12px;">
              <div style="width:140px; font-size:13px; font-weight:500; flex-shrink:0;">기본 추론 모델</div>
              <input type="text" class="glass-input setting-input" data-key="default_model"
                placeholder="예: qwen3.6:latest, openai/gpt-4o-mini"
                value="${defaultModel}"
                style="flex:1; font-size:13px;">
            </div>
          </div>
        `;

        // ═══ 3. 웹 검색 엔진 ═══
        const searchEngine = savedSettings.search_engine || 'searxng';
        html += `
          <div class="glass-panel" style="padding: 24px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🔍</span> 웹 검색 엔진
            </h3>
            <div style="display:flex; flex-direction:column; gap:10px;">
              <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:13px;">
                <input type="radio" name="search_engine" value="searxng" ${searchEngine === 'searxng' ? 'checked' : ''}>
                SearxNG (메타 검색 — Google+Bing+DDG 집계, 로컬)
              </label>
              <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:13px;">
                <input type="radio" name="search_engine" value="duckduckgo" ${searchEngine === 'duckduckgo' ? 'checked' : ''}>
                DuckDuckGo (단일 엔진, 간단)
              </label>
              <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:13px;">
                <input type="radio" name="search_engine" value="jina" ${searchEngine === 'jina' ? 'checked' : ''}>
                Jina AI (시맨틱 검색)
              </label>
            </div>
          </div>
        `;

        // ═══ 4. 비용 제어 ═══
        const dailyBudget = savedSettings.daily_budget_usd || '50';
        const hourlyLimit = savedSettings.hourly_action_limit || '100';
        html += `
          <div class="glass-panel" style="padding: 24px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">💰</span> 비용 제어
            </h3>
            <div style="display:flex; flex-direction:column; gap:14px;">
              <div style="display:flex; align-items:center; gap:12px;">
                <div style="width:160px; font-size:13px; font-weight:500; flex-shrink:0;">일일 예산 (USD)</div>
                <input type="number" class="glass-input setting-input" data-key="daily_budget_usd"
                  value="${dailyBudget}" min="0" step="1"
                  style="width:100px; font-size:13px;">
                <span style="font-size:11px; color:var(--text-muted,#565f89);">초과 시 LLM 호출 차단</span>
              </div>
              <div style="display:flex; align-items:center; gap:12px;">
                <div style="width:160px; font-size:13px; font-weight:500; flex-shrink:0;">시간당 액션 한도</div>
                <input type="number" class="glass-input setting-input" data-key="hourly_action_limit"
                  value="${hourlyLimit}" min="1" step="1"
                  style="width:100px; font-size:13px;">
                <span style="font-size:11px; color:var(--text-muted,#565f89);">분당 호출 수 제한</span>
              </div>
            </div>
          </div>
        `;

        // ═══ 5. 서버 구성 (읽기 전용) ═══
        html += `
          <div class="glass-panel" style="padding: 24px; opacity:0.8;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🖥</span> 서버 구성 (읽기 전용)
            </h3>
            <div style="display: grid; grid-template-columns: 150px 1fr; gap: 12px; align-items: center; font-size: 14px;">
              <div style="color: var(--text-secondary); font-weight: 500;">호스트</div>
              <div>${cfg.server?.host || '127.0.0.1'}</div>
              <div style="color: var(--text-secondary); font-weight: 500;">포트</div>
              <div>${cfg.server?.port || '8000'}</div>
              <div style="color: var(--text-secondary); font-weight: 500;">API 엔진</div>
              <div>${cfg.model?.provider || 'openrouter'}</div>
            </div>
          </div>
        `;

        // ═══ 저장 버튼 ═══
        html += `
          <div style="display:flex; gap:12px; justify-content:flex-end;">
            <button id="settings-reset-btn" class="btn" style="background:transparent; border:1px solid var(--glass-border); padding:10px 20px; border-radius:8px; cursor:pointer; font-size:13px; color:var(--text-secondary);">
              초기화
            </button>
            <button id="settings-save-btn" class="btn" style="background:var(--accent-color,#7c6aef); padding:10px 24px; border-radius:8px; cursor:pointer; font-size:13px; color:white; border:none; font-weight:600;">
              💾 설정 저장
            </button>
          </div>
          <div id="settings-status" style="font-size:12px; text-align:right; min-height:18px;"></div>
        `;

        container.innerHTML = html;

        // ═══ 이벤트 핸들러 ═══

        // 저장 버튼
        document.getElementById('settings-save-btn').addEventListener('click', () => {
          const inputs = container.querySelectorAll('.setting-input');
          const settings = {};
          inputs.forEach(input => {
            const key = input.dataset.key;
            const val = input.value.trim();
            if (val) settings[key] = val;
          });

          // 라디오 버튼
          const searchRadio = container.querySelector('input[name="search_engine"]:checked');
          if (searchRadio) settings.search_engine = searchRadio.value;

          // localStorage에 저장
          localStorage.setItem('agk_user_settings', JSON.stringify(settings));

          // PIN 헤더 확보 (전역 인터셉터 백업)
          const pin = localStorage.getItem('ag_access_pin') || '0000';
          const saveBtn = document.getElementById('settings-save-btn');
          const status = document.getElementById('settings-status');
          saveBtn.textContent = '⏳ 저장 중...';
          saveBtn.disabled = true;

          // .env 파일에 저장 (백엔드 API 호출 — PIN 명시적 포함)
          fetch('/api/settings/env', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Access-Pin': pin,
            },
            body: JSON.stringify(settings),
          })
          .then(res => res.json())
          .then(data => {
            if (data.ok) {
              status.innerHTML = '<span style="color:#10b981;">✅ 저장 완료! ' + (data.updated || 0) + '개 항목이 .env에 저장되었습니다.</span>';
              if (window.showToast) window.showToast('설정이 저장되었습니다', 'success');
            } else {
              status.innerHTML = '<span style="color:#f59e0b;">⚠️ ' + (data.error || data.detail || '저장 실패 — PIN을 확인하세요') + '</span>';
            }
          })
          .catch((err) => {
            // 백엔드 API가 실패해도 localStorage에는 저장됨
            status.innerHTML = '<span style="color:#f59e0b;">⚠️ localStorage에 저장됨 (.env 동기화 실패: ' + err.message + ')</span>';
          })
          .finally(() => {
            saveBtn.textContent = '💾 설정 저장';
            saveBtn.disabled = false;
          });
        });

        // 초기화 버튼
        document.getElementById('settings-reset-btn').addEventListener('click', () => {
          if (confirm('모든 설정을 초기화하시겠습니까?')) {
            localStorage.removeItem('agk_user_settings');
            location.reload();
          }
        });
      })
      .catch(err => {
        container.innerHTML = `<div class="error-state">설정 로드 실패: ${err.message}</div>`;
      });
  }
};
