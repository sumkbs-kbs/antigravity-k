export const ModelsPage = {
  render: () => `
    <div class="page-container">
      <div class="page-header">
        <h2>모델 관리 <span>Models</span></h2>
        <p class="page-subtitle">설치된 로컬 모델 목록을 확인하고 리소스를 관리하세요.</p>
      </div>
      <div id="models-grid" class="models-grid">
        <div class="loading-state">로딩 중...</div>
      </div>
    </div>
  `,
  init: () => {
    const grid = document.getElementById('models-grid');
    fetch('/v1/models')
      .then(res => res.json())
      .then(data => {
        if (!data || !data.data || data.data.length === 0) {
          grid.innerHTML = '<div class="empty-state">설치된 모델이 없습니다.</div>';
          return;
        }
        grid.innerHTML = '';
        data.data.forEach(model => {
          grid.innerHTML += `
            <div class="glass-card">
              <div class="card-header">
                <h3>${model.id}</h3>
                <span class="status-badge active">Active</span>
              </div>
              <div class="card-body">
                <p><strong>소유자:</strong> ${model.owned_by || 'system'}</p>
                <p><strong>생성일:</strong> ${new Date(model.created * 1000).toLocaleDateString()}</p>
              </div>
              <div class="card-footer">
                <button class="glass-btn primary">설정 변경</button>
                <button class="glass-btn danger">삭제</button>
              </div>
            </div>
          `;
        });
      })
      .catch(err => {
        console.error(err);
        grid.innerHTML = `<div class="error-state">모델 정보를 불러오는 중 오류가 발생했습니다.</div>`;
      });
  }
};
