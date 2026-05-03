export const FinetunePage = {
  render: () => `
    <div class="page-container">
      <div class="page-header">
        <h2>파인튜닝 <span>Fine-Tuning</span></h2>
        <p class="page-subtitle">보유한 데이터셋으로 로컬 모델을 학습시키고 맞춤화하세요.</p>
      </div>
      
      <div class="finetune-layout">
        <div class="finetune-sidebar">
          <div class="glass-card">
            <div class="card-header">
              <h3>학습 설정</h3>
            </div>
            <div class="card-body form-group">
              <label>기반 모델</label>
              <select class="glass-select full-width">
                <option>qwen2.5-coder-7b-instruct</option>
                <option>llama-3.1-8b</option>
              </select>
              
              <label>에포크 (Epochs)</label>
              <input type="number" class="glass-input full-width" value="3">
              
              <label>배치 사이즈 (Batch Size)</label>
              <input type="number" class="glass-input full-width" value="4">
              
              <label>학습률 (Learning Rate)</label>
              <input type="text" class="glass-input full-width" value="2e-5">
              
              <button class="glass-btn primary full-width" style="margin-top: 16px;">학습 시작</button>
            </div>
          </div>
        </div>
        
        <div class="finetune-main">
          <div class="glass-card upload-zone">
            <div class="upload-icon">📂</div>
            <h3>데이터셋 업로드</h3>
            <p>JSONL 형식의 대화 데이터를 드래그 앤 드롭하세요.</p>
            <button class="glass-btn">파일 선택</button>
          </div>
          
          <div class="glass-card chart-zone">
            <div class="card-header">
              <h3>학습 진행 상황</h3>
              <span class="status-badge pending">대기 중</span>
            </div>
            <div class="chart-placeholder">
              학습이 시작되면 진행률과 Loss 차트가 여기에 표시됩니다.
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  init: () => {
    // Add logic later
  }
};
