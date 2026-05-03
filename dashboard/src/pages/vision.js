export const VisionPage = {
  render: () => `
    <div class="page-container" style="max-width: 1000px;">
      <div class="page-header" style="margin-bottom: 24px;">
        <h2>시각 인지 <span>Vision</span></h2>
        <p class="page-subtitle">멀티모달 모델(Llava, Claude-3.5-Sonnet)을 활용해 이미지를 분석합니다.</p>
      </div>

      <div class="glass-panel" style="padding: 24px; display: flex; flex-direction: column; gap: 24px;">
        <!-- 이미지 업로드 영역 -->
        <div id="vision-dropzone" style="border: 2px dashed var(--glass-border); border-radius: 8px; padding: 40px; text-align: center; cursor: pointer; transition: all 0.2s;">
          <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;">📸</div>
          <h3 style="margin-bottom: 8px; color: var(--text-primary);">이미지를 드래그하거나 클릭하여 업로드</h3>
          <p style="color: var(--text-secondary); font-size: 14px;">JPG, PNG, WebP 지원 (최대 5MB)</p>
          <input type="file" id="vision-file-input" accept="image/*" style="display: none;">
        </div>

        <!-- 이미지 미리보기 영역 -->
        <div id="vision-preview-container" style="display: none; position: relative;">
          <img id="vision-preview" style="max-width: 100%; max-height: 400px; border-radius: 8px; border: 1px solid var(--glass-border);" />
          <button id="vision-clear-btn" class="icon-btn" style="position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);">✕</button>
        </div>

        <!-- 프롬프트 입력 영역 -->
        <div style="display: flex; gap: 12px; align-items: flex-start;">
          <textarea id="vision-prompt" class="glass-input" rows="3" placeholder="이미지에 대해 물어보세요... (예: 이 아키텍처 다이어그램을 설명해줘)" style="flex: 1; resize: vertical; min-height: 80px;"></textarea>
          <button id="vision-send-btn" class="glass-btn primary" style="height: 80px; padding: 0 24px; display: flex; flex-direction: column; gap: 8px;">
            <span style="font-size: 20px;">✨</span>
            <span>분석</span>
          </button>
        </div>

        <!-- 결과 출력 영역 -->
        <div id="vision-result" class="glass-panel" style="display: none; padding: 20px; background: rgba(0,0,0,0.2); min-height: 100px;">
          <!-- 결과 내용이 여기에 들어감 -->
        </div>
      </div>
    </div>
  `,
  init: () => {
    const dropzone = document.getElementById('vision-dropzone');
    const fileInput = document.getElementById('vision-file-input');
    const previewContainer = document.getElementById('vision-preview-container');
    const preview = document.getElementById('vision-preview');
    const clearBtn = document.getElementById('vision-clear-btn');
    const sendBtn = document.getElementById('vision-send-btn');
    const promptInput = document.getElementById('vision-prompt');
    const resultDiv = document.getElementById('vision-result');

    let currentFile = null;

    dropzone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFile(e.target.files[0]);
      }
    });

    clearBtn.addEventListener('click', () => {
      currentFile = null;
      fileInput.value = '';
      previewContainer.style.display = 'none';
      dropzone.style.display = 'block';
    });

    function handleFile(file) {
      if (!file.type.startsWith('image/')) return;
      currentFile = file;
      
      const reader = new FileReader();
      reader.onload = (e) => {
        preview.src = e.target.result;
        dropzone.style.display = 'none';
        previewContainer.style.display = 'inline-block';
      };
      reader.readAsDataURL(file);
    }

    sendBtn.addEventListener('click', () => {
      if (!currentFile) {
        alert('먼저 이미지를 업로드해주세요.');
        return;
      }
      const text = promptInput.value.trim() || "What's in this image?";
      
      resultDiv.style.display = 'block';
      resultDiv.innerHTML = '<div style="display:flex; align-items:center; gap:8px;"><span class="spinner-mini"></span><span>이미지 분석 중... (로컬 Vision 모델이 호출됩니다)</span></div>';
      
      // Simulate API call
      setTimeout(() => {
        resultDiv.innerHTML = `
          <h4 style="margin-bottom:12px; color:var(--accent-color);">분석 결과</h4>
          <p style="line-height:1.6; color:#ddd;">현재 Vision 백엔드 연동이 준비 중입니다. 업로드된 이미지는 <strong>${currentFile.name}</strong> (${(currentFile.size/1024).toFixed(1)} KB) 이며, 프롬프트는 <em>"${text}"</em> 입니다.</p>
        `;
      }, 2000);
    });
  }
};
