/**
 * EmptyState — Welcome screen with example prompt chips
 */

import React from 'react';

interface Props {
  onExampleClick: (text: string) => void;
}

const EXAMPLES = [
  { icon: '📁', text: '파일 목록 보여줘' },
  { icon: '🌤️', text: '오늘 서울 날씨 알려줘' },
  { icon: '🤖', text: '니가 할 수 있는 게 뭐야?' },
  { icon: '🔍', text: '이 프로젝트 코드 리뷰해줘' },
];

const EmptyState: React.FC<Props> = ({ onExampleClick }) => {
  return (
    <div className="empty-state-container">
      <div className="empty-state-logo">🚀</div>
      <div className="empty-state-title">Antigravity-K에 오신 것을 환영합니다</div>
      <div className="empty-state-subtitle">
        로컬 AI 엔지니어링 에이전트입니다. 코드 작성, 파일 편집, 웹 검색,
        날씨/주가 조회 등 다양한 작업을 도와드릴 수 있습니다.
      </div>
      <div className="empty-state-chips">
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            className="example-chip"
            onClick={() => onExampleClick(ex.text)}
          >
            {ex.icon} {ex.text}
          </button>
        ))}
      </div>
    </div>
  );
};

export default EmptyState;
