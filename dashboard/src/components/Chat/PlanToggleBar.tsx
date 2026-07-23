/**
 * PlanToggleBar — Mode toggle bar below chat input
 */

import React from 'react';
import { useChatStore } from '../../stores/chatStore';

const PlanToggleBar: React.FC = () => {
  const { selectedModel, isPlanMode, isTddMode, setPlanMode, setTddMode } = useChatStore();

  const modelName = selectedModel === 'default' ? 'Default Local Model' : selectedModel;

  return (
    <div className="plan-toggle-bar">
      <div className="plan-model-info">
        <span>⚡</span>
        <span>{modelName}</span>
      </div>
      <div className="plan-controls">
        {/* Auto Mode (always active) */}
        <div className="plan-toggle active" title="Autonomous Mode: AI가 툴을 자율적으로 실행합니다">
          <span className="toggle-dot" style={{ background: 'var(--accent-color)' }} />
          <span>🤖 Auto</span>
        </div>

        {/* Plan Mode Toggle */}
        <div
          className={`plan-toggle ${isPlanMode ? 'active' : ''}`}
          onClick={() => setPlanMode(!isPlanMode)}
          title="Plan Mode: AI가 먼저 구현 계획을 수립합니다"
          role="button"
          tabIndex={0}
        >
          <span className="toggle-dot" />
          <span>📋 Plan</span>
        </div>

        {/* TDD Mode Toggle */}
        <div
          className={`plan-toggle ${isTddMode ? 'active' : ''}`}
          onClick={() => setTddMode(!isTddMode)}
          title="TDD Mode: 다중 모델 경쟁 기반으로 테스트 주도 코딩을 수행합니다"
          role="button"
          tabIndex={0}
        >
          <span className="toggle-dot" style={{ background: 'var(--success-color)' }} />
          <span>🧪 TDD Mode</span>
        </div>
      </div>
    </div>
  );
};

export default PlanToggleBar;
