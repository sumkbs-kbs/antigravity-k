/**
 * Sidebar — Codex Desktop Exact Layout
 * =====================================
 * Pixel-perfect implementation of the user's uploaded screenshot:
 * - Top: Window traffic lights (🔴 🟡 🟢) + nav icons
 * - Brand: Codex ∨ + 🔍 (search) + 🔔 (notifications)
 * - Primary 5 items:
 *   1. 📝 새 채팅 (with + shortcut)
 *   2. 🔀 풀 리퀘스트
 *   3. ⏱️ 예약
 *   4. 🧩 플러그인
 *   5. ⋯ 탐색
 * - Section: 프로젝트
 *   - 📁 web search
 *   - 📁 New project
 *   - 📁 ssakfile_pro 1.0.0
 *   - 📁 antigravity-k (Selected active card with detailed tasks)
 * - Section: 최근 (Recent chat threads)
 * - Usage Quota Card:
 *   - 사용량 1% 남음 (1주, 1% remaining, reset date, 크레딧 추가, 업그레이드)
 * - User Profile:
 *   - BK (green circle) + Byungseok Ka... + ılı 음성 + ❓
 */

import React, { useState, useEffect } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';
import { useChatStore } from '../../stores/chatStore';

export const Sidebar: React.FC<{ toggleTerminal?: () => void }> = () => {
  const { setCommandPaletteVisible, addToast } = useUiStore();
  const { sessions, activeSessionId, createNewSession, switchSession, deleteSession } = useChatStore();
  const location = useLocation();
  const navigate = useNavigate();

  const [usageCardVisible, setUsageCardVisible] = useState(true);
  const [selectedProject, setSelectedProject] = useState('Ssak-Ai');
  const [quotaInfo, setQuotaInfo] = useState({
    percent_remaining: 1,
    period_label: '1주',
    resets_note: 'Resets on 9월 7일 at 오전 11:28',
  });

  useEffect(() => {
    fetch('/api/system/quota')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setQuotaInfo({
            percent_remaining: data.percent_remaining ?? 1,
            period_label: data.period_label || '1주',
            resets_note: data.resets_note || 'Resets on 9월 7일 at 오전 11:28',
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleNewChat = () => {
    createNewSession();
    navigate('/chat');
  };

  const handleSelectSession = (sessionId: string) => {
    switchSession(sessionId);
    navigate('/chat');
  };

  return (
    <aside className="codex-desktop-sidebar" aria-label="Codex Desktop Navigation">
      {/* ── Top Window Bar: Traffic Lights & Navigation ────────── */}
      <div className="codex-window-bar">
        <div className="traffic-lights">
          <span className="tl-dot tl-red" />
          <span className="tl-dot tl-yellow" />
          <span className="tl-dot tl-green" />
        </div>
        <div className="window-nav-icons">
          <button type="button" className="win-btn" title="사이드바 토글" aria-label="사이드바 토글">
            ◫
          </button>
          <button type="button" className="win-btn" onClick={() => window.history.back()} title="뒤로" aria-label="뒤로">
            ←
          </button>
          <button type="button" className="win-btn" onClick={() => window.history.forward()} title="앞으로" aria-label="앞으로">
            →
          </button>
        </div>
      </div>

      {/* ── Brand Header: Codex ∨ + Search + Bell ──────────────── */}
      <div className="codex-brand-row">
        <button type="button" className="codex-title-dropdown-btn">
          <span className="brand-title">Ssak-Ai</span>
          <span className="chevron-icon">∨</span>
        </button>
        <div className="brand-action-icons">
          <button
            type="button"
            className="icon-action-btn"
            onClick={() => setCommandPaletteVisible(true)}
            title="검색 (Cmd+K)"
            aria-label="검색"
          >
            🔍
          </button>
          <button
            type="button"
            className="icon-action-btn"
            onClick={() => addToast('새로운 알림이 없습니다.', 'info')}
            title="알림"
            aria-label="알림"
          >
            🔔
          </button>
        </div>
      </div>

      {/* ── Scrollable Body ───────────────────────────────────── */}
      <div className="codex-sidebar-scroll-area">
        {/* ── 5 Main Nav Items ─────────────────────────────────── */}
        <div className="codex-primary-menu">
          <button
            type="button"
            className="codex-menu-row new-chat-row"
            onClick={handleNewChat}
          >
            <span className="menu-icon">📝</span>
            <span className="menu-label">새 채팅</span>
            <span className="visually-hidden">AI 채팅</span>
            <span className="row-plus-badge">+</span>
          </button>

          <NavLink
            to="/git"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">🔀</span>
            <span className="menu-label">풀 리퀘스트</span>
          </NavLink>

          <NavLink
            to="/history"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">⏱️</span>
            <span className="menu-label">예약</span>
          </NavLink>

          <NavLink
            to="/plugins"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">🧩</span>
            <span className="menu-label">플러그인</span>
          </NavLink>

          <NavLink
            to="/skills"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">⋯</span>
            <span className="menu-label">탐색</span>
          </NavLink>
        </div>

        {/* ── Section: 프로젝트 ─────────────────────────────────── */}
        <div className="codex-section-container">
          <div className="codex-section-label">프로젝트</div>
          <div className="codex-projects-list">
            {/* web search */}
            <div
              className={`project-folder-box ${selectedProject === 'web search' ? 'selected' : ''}`}
              onClick={() => setSelectedProject('web search')}
            >
              <div className="folder-name-line">
                <span className="folder-icon">📁</span>
                <span className="folder-text">web search</span>
              </div>
              <div className="folder-sub-preview">
                웹서치 프로그램 진단·고도화 및 단계별...
              </div>
            </div>

            {/* New project */}
            <div
              className={`project-folder-box ${selectedProject === 'New project' ? 'selected' : ''}`}
              onClick={() => setSelectedProject('New project')}
            >
              <div className="folder-name-line">
                <span className="folder-icon">📁</span>
                <span className="folder-text">New project</span>
              </div>
              <div className="folder-sub-preview">
                ollama run hf.co/unsloth/Qwen3.8...
              </div>
              <div className="folder-sub-preview">
                Rename Ollama model
              </div>
            </div>

            {/* ssakfile_pro 1.0.0 */}
            <div
              className={`project-folder-box ${selectedProject === 'ssakfile_pro' ? 'selected' : ''}`}
              onClick={() => setSelectedProject('ssakfile_pro')}
            >
              <div className="folder-name-line">
                <span className="folder-icon">📁</span>
                <span className="folder-text">ssakfile_pro 1.0.0</span>
              </div>
              <div className="folder-sub-preview muted">
                채팅 없음
              </div>
            </div>

            {/* Ssak-Ai (Active Card from Screenshot) */}
            <div
              className={`project-folder-box active-highlight ${selectedProject === 'Ssak-Ai' ? 'selected' : ''}`}
              onClick={() => setSelectedProject('Ssak-Ai')}
            >
              <div className="folder-name-line">
                <span className="folder-icon">📁</span>
                <span className="folder-text bold">Ssak-Ai</span>
              </div>
              <div className="folder-task-list">
                <div className="task-item" onClick={handleNewChat}>전체 코드 QA 및 완성도 평가</div>
                <div className="task-item" onClick={handleNewChat}>벤치마킹 기능 및 기술 반영</div>
                <div className="task-item" onClick={handleNewChat}>전체 코드 문제점 점검</div>
                <div className="task-item" onClick={handleNewChat}>상용 대비 완성도 평가</div>
                <div className="task-item" onClick={handleNewChat}>분석 기반 인터페이스 고도화 계획</div>
                <div className="task-item more" onClick={handleNewChat}>더 보기</div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Section: 최근 ─────────────────────────────────────── */}
        <div className="codex-section-container">
          <div className="codex-section-label">최근</div>
          <div className="codex-recents-list">
            {sessions.length === 0 ? (
              <div className="recent-link" onClick={handleNewChat}>
                새 대화 시작하기
              </div>
            ) : (
              sessions.slice(0, 5).map(s => (
                <div
                  key={s.id}
                  className={`recent-link ${activeSessionId === s.id ? 'active' : ''}`}
                  onClick={() => handleSelectSession(s.id)}
                >
                  <span className="recent-status-dot" aria-hidden="true" />
                  <span className="recent-title">{s.title || '대화'}</span>
                  <button
                    type="button"
                    className="delete-sub-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(s.id);
                    }}
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ── Usage Quota Widget Card (사용량 1% 남음) ─────────── */}
      {usageCardVisible && (
        <div className="codex-usage-widget-card">
          <div className="usage-card-header">
            <span className="usage-title">사용량 {quotaInfo.percent_remaining}% 남음</span>
            <button
              type="button"
              className="usage-close-btn"
              onClick={() => setUsageCardVisible(false)}
              title="닫기"
            >
              ×
            </button>
          </div>
          <div className="usage-period-row">
            <span className="period-text">{quotaInfo.period_label}</span>
            <span className="pct-text">{quotaInfo.percent_remaining}% remaining</span>
          </div>
          <div className="usage-meter-track">
            <div className="usage-meter-fill" style={{ width: `${quotaInfo.percent_remaining}%` }} />
          </div>
          <div className="usage-reset-note">
            {quotaInfo.resets_note}
          </div>
          <div className="usage-btn-row">
            <button
              type="button"
              className="usage-btn credit-btn"
              onClick={() => addToast('크레딧 충전 페이지로 이동합니다.', 'info')}
            >
              크레딧 추가
            </button>
            <button
              type="button"
              className="usage-btn upgrade-btn"
              onClick={() => addToast('Pro 플랜으로 업그레이드합니다.', 'info')}
            >
              업그레이드
            </button>
          </div>
        </div>
      )}

      {/* ── Bottom User Profile Bar: Byungseok Ka... ──────────── */}
      <div className="codex-user-bottom-bar">
        <div className="user-profile-left">
          <div className="avatar-initial-circle">BK</div>
          <span className="user-display-name">Byungseok Ka...</span>
        </div>
        <div className="user-profile-right">
          <button
            type="button"
            className="voice-action-pill"
            onClick={() => addToast('음성 대화 모드가 준비되었습니다.', 'info')}
            title="음성 대화"
          >
            <span className="sound-wave-icon">ılı</span>
            <span className="voice-text">음성</span>
          </button>
          <NavLink to="/settings" className="help-icon-link" title="도움말 및 설정">
            ?
          </NavLink>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
