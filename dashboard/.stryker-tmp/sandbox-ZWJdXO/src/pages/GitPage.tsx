/**
 * GitPage — Full-page Git GUI
 * ============================
 * Simple wrapper page for the GitPanel component.
 * Provides the page header and container layout.
 */
// @ts-nocheck


import React from 'react';
import GitPanel from '../components/Git/GitPanel';

const GitPage: React.FC = () => {
  return (
    <div className="page-container full-height-page" style={{ padding: 0, overflow: 'hidden' }}>
      <div className="git-page-header">
        <h2>🐙 Git <span>소스 제어</span></h2>
        <p className="page-subtitle">브랜치 관리, 변경 사항 스테이징, 커밋, 히스토리 조회</p>
      </div>
      <div className="git-page-content" style={{ flex: 1, overflow: 'hidden', padding: '0 16px 16px' }}>
        <GitPanel />
      </div>
    </div>
  );
};

export default GitPage;
