export const SearchPage = () => {
  const container = document.createElement('div');
  container.className = 'page-container';
  container.innerHTML = `
    <div class="search-hero">
      <h2>웹 & 코드 인텔리전스 검색</h2>
      <p>방대한 코드베이스와 문서를 자연어로 탐색하세요.</p>
      
      <div class="search-bar-wrapper glass-panel">
        <span class="search-icon">🔍</span>
        <input type="text" id="global-search-input" placeholder="함수, 클래스 이름, 혹은 작동 방식을 입력해보세요..." class="hero-search-input">
        <button class="glass-btn primary" id="global-search-btn">검색</button>
      </div>
    </div>
    
    <div class="search-filters">
      <button class="filter-chip active">전체</button>
      <button class="filter-chip">코드베이스</button>
      <button class="filter-chip">마크다운 문서</button>
      <button class="filter-chip">웹 데이터</button>
    </div>
    
    <div class="search-results-area" id="search-results">
      <div class="empty-search-state">
        검색어를 입력하시면 관련된 코드 스니펫과 문서가 이곳에 나타납니다.
      </div>
    </div>
  `;
  
  setTimeout(() => {
    const btn = container.querySelector('#global-search-btn');
    const input = container.querySelector('#global-search-input');
    const results = container.querySelector('#search-results');
    
    const performSearch = () => {
      const q = input.value.trim();
      if (!q) return;
      results.innerHTML = '<div class="loading-state">검색 중...</div>';
      
      // Simulate search results for now
      setTimeout(() => {
        results.innerHTML = `
          <div class="result-card glass-panel">
            <div class="result-header">
              <span class="result-type">Code</span>
              <span class="result-path">src/antigravity_k/engine/orchestrator.py</span>
            </div>
            <div class="result-title">OrchestratorAgent 클래스</div>
            <pre class="result-snippet"><code>def run_sync(self, messages, target_model, max_steps=15):\n    # 동기식 실행\n    pass</code></pre>
          </div>
          <div class="result-card glass-panel">
            <div class="result-header">
              <span class="result-type">Document</span>
              <span class="result-path">README.md</span>
            </div>
            <div class="result-title">에이전트 사용 방법</div>
            <div class="result-snippet">에이전트 모드는 기본적으로 활성화되어 있으며, 자연어를 통한 도구 사용을 지원합니다.</div>
          </div>
        `;
      }, 800);
    };
    
    btn.addEventListener('click', performSearch);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') performSearch();
    });
  }, 0);
  
  return container;
};
