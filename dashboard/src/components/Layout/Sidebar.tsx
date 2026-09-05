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
 *   - 📁 Ssak-Ai (Selected active card with detailed tasks)
 * - Section: 최근 (Recent chat threads)
 * - Usage Quota Card:
 *   - 사용량 1% 남음 (1주, 1% remaining, reset date, 크레딧 추가, 업그레이드)
 * - User Profile:
 *   - BK (green circle) + Byungseok Ka... + ılı 음성 + ❓
 */

import React, { useState, useEffect, useCallback } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';
import { useChatStore } from '../../stores/chatStore';
import { useFileStore } from '../../stores/fileStore';
import { useGitStore } from '../../stores/gitStore';
import { createAccessPinHeaders } from '../../utils/accessPinCredential';
import { ProjectListResponseSchema, type ProjectRecord } from '../../api/clientSchema';

export const Sidebar: React.FC<{ toggleTerminal?: () => void }> = () => {
  const { setCommandPaletteVisible, setFolderBrowserVisible, addToast } = useUiStore();
  const { sessions, activeSessionId, createNewSession, switchSession, deleteSession, updateSessionTitle } = useChatStore();
  const { setWorkspacePath, refreshTree } = useFileStore();
  const gitStatus = useGitStore(s => s.status);
  const fetchGitStatus = useGitStore(s => s.fetchStatus);
  const location = useLocation();
  const navigate = useNavigate();

  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitleText, setEditTitleText] = useState('');

  useEffect(() => {
    fetchGitStatus();
  }, [fetchGitStatus]);

  const fetchProjects = useCallback(() => {
    fetch('/api/projects', { headers: createAccessPinHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(raw => {
        if (raw) {
          const parsed = ProjectListResponseSchema.safeParse(raw);
          if (parsed.success && parsed.data.projects.length > 0) {
            setProjects(parsed.data.projects);
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchProjects();
    const handleProjectsChanged = () => fetchProjects();
    window.addEventListener('agk:projects-changed', handleProjectsChanged);
    return () => window.removeEventListener('agk:projects-changed', handleProjectsChanged);
  }, [fetchProjects]);

  const handleSwitchProject = async (proj: ProjectRecord) => {
    try {
      const res = await fetch('/api/projects/switch', {
        method: 'POST',
        headers: createAccessPinHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ project_id: proj.id }),
      });
      if (res.ok) {
        setWorkspacePath(proj.path);
        localStorage.setItem('agk_active_project', proj.path);
        addToast(`📂 '${proj.name}' 프로젝트로 전환되었습니다.`, 'success');
        refreshTree();
        fetchProjects();
      } else {
        addToast('프로젝트 전환에 실패했습니다.', 'error');
      }
    } catch (err) {
      addToast(`프로젝트 전환 오류: ${err instanceof Error ? err.message : String(err)}`, 'error');
    }
  };

  const handleDeleteProject = async (e: React.MouseEvent, proj: ProjectRecord) => {
    e.stopPropagation();
    if (!window.confirm(`'${proj.name}' 프로젝트를 목록에서 제외하시겠습니까?\n(실제 로컬 파일은 삭제되지 않습니다)`)) {
      return;
    }
    try {
      const res = await fetch(`/api/projects/${proj.id}`, {
        method: 'DELETE',
        headers: createAccessPinHeaders(),
      });
      if (res.ok) {
        addToast(`'${proj.name}' 프로젝트가 목록에서 제외되었습니다.`, 'info');
        const updatedRes = await fetch('/api/projects', { headers: createAccessPinHeaders() });
        if (updatedRes.ok) {
          const raw = await updatedRes.json();
          const parsed = ProjectListResponseSchema.safeParse(raw);
          if (parsed.success && parsed.data.projects.length > 0) {
            setProjects(parsed.data.projects);
            const newActive = parsed.data.projects.find(p => p.is_active) || parsed.data.projects[0];
            if (newActive && proj.is_active) {
              setWorkspacePath(newActive.path);
              localStorage.setItem('agk_active_project', newActive.path);
              refreshTree();
            }
          }
        }
      } else {
        addToast('프로젝트 제거에 실패했습니다.', 'error');
      }
    } catch {
      addToast('프로젝트 제거 중 오류가 발생했습니다.', 'error');
    }
  };

  const handleStartRename = (e: React.MouseEvent, s: { id: string; title?: string }) => {
    e.stopPropagation();
    setEditingSessionId(s.id);
    setEditTitleText(s.title || '새 대화');
  };

  const handleSaveRename = (sessionId: string) => {
    const trimmed = editTitleText.trim();
    if (trimmed) {
      updateSessionTitle(sessionId, trimmed);
      addToast('대화 제목이 변경되었습니다.', 'info');
    }
    setEditingSessionId(null);
  };

  const handleDeleteSession = (e: React.MouseEvent, s: { id: string; title?: string }) => {
    e.stopPropagation();
    const name = s.title || '대화';
    if (window.confirm(`'${name}' 대화를 삭제하시겠습니까?`)) {
      deleteSession(s.id);
      addToast('대화가 삭제되었습니다.', 'info');
    }
  };

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
      {/* ── Brand Header: Ssak-Ai + Search + Bell ──────────────── */}
      <div className="codex-brand-row">
        <button type="button" className="codex-title-dropdown-btn">
          <span className="brand-title">Ssak-Ai</span>
          <span className="terminal-slash" style={{ marginLeft: 4 }}>// v0.8.0</span>
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
        {/* ── 5 Main Nav Items (TERMINAL-7 style) ───────────────── */}
        <div className="codex-primary-menu">
          <button
            type="button"
            className="codex-menu-row new-chat-row"
            onClick={handleNewChat}
          >
            <span className="menu-icon">📝</span>
            <span className="menu-label">// 01 · 새 채팅</span>
            <span className="visually-hidden">AI 채팅</span>
            <span className="row-plus-badge">+</span>
          </button>

          <NavLink
            to="/git"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">🔀</span>
            <span className="menu-label">// 02 · 풀 리퀘스트</span>
            <span className="visually-hidden">Git</span>
          </NavLink>

          <NavLink
            to="/history"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">⏱️</span>
            <span className="menu-label">// 03 · 예약 / 실행</span>
          </NavLink>

          <NavLink
            to="/plugins"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">🧩</span>
            <span className="menu-label">// 04 · 플러그인</span>
          </NavLink>

          <NavLink
            to="/skills"
            className={({ isActive }) => `codex-menu-row ${isActive ? 'active' : ''}`}
          >
            <span className="menu-icon">⋯</span>
            <span className="menu-label">// 05 · 탐색 / 스킬</span>
          </NavLink>
        </div>

        {/* ── Section: 프로젝트 ─────────────────────────────────── */}
        <div className="codex-section-container">
          <div className="codex-section-label-row">
            <span className="codex-section-label">// PROJECTS</span>
            <button
              type="button"
              className="project-add-btn"
              title="새 프로젝트 폴더 열기/등록"
              aria-label="새 프로젝트 추가"
              onClick={() => setFolderBrowserVisible(true)}
            >
              +
            </button>
          </div>
          <div className="codex-projects-list">
            {projects.length === 0 ? (
              <div
                className="project-folder-box active-highlight selected"
                onClick={() => setFolderBrowserVisible(true)}
              >
                <div className="folder-name-line">
                  <span className="folder-icon">📁</span>
                  <span className="folder-text bold">프로젝트 열기</span>
                </div>
                <div className="folder-sub-preview">
                  클릭하여 로컬 폴더를 프로젝트로 등록하세요
                </div>
              </div>
            ) : (
              projects.map((proj) => (
                <div
                  key={proj.id}
                  className={`project-folder-box ${proj.is_active ? 'active-highlight selected' : ''}`}
                  onClick={() => handleSwitchProject(proj)}
                  title={`${proj.name} (${proj.path})`}
                >
                  <div className="folder-name-line">
                    <span className="folder-icon">📁</span>
                    <span className={`folder-text ${proj.is_active ? 'bold' : ''}`}>{proj.name}</span>
                    {proj.is_active && (
                      <span
                        className="project-git-pill"
                        style={{
                          marginLeft: 'auto',
                          fontSize: '10px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          padding: '1px 6px',
                          borderRadius: '10px',
                          background: 'rgba(56, 189, 248, 0.12)',
                          color: '#38bdf8',
                          border: '1px solid rgba(56, 189, 248, 0.25)',
                        }}
                        title={`Git Branch: ${gitStatus.branch || 'main'}`}
                      >
                        ⎇ {gitStatus.branch || 'main'}
                        {gitStatus.counts.total > 0 && (
                          <span style={{ color: '#fbbf24' }}>●{gitStatus.counts.total}</span>
                        )}
                      </span>
                    )}
                    {projects.length > 1 && (
                      <button
                        type="button"
                        className="project-remove-btn"
                        title="프로젝트 목록에서 제외"
                        aria-label={`${proj.name} 프로젝트 제거`}
                        onClick={(e) => handleDeleteProject(e, proj)}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  <div className="folder-sub-preview">
                    {proj.path}
                  </div>
                  {proj.is_active && (
                    <div className="folder-task-list" onClick={(e) => e.stopPropagation()}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '3px 0',
                          fontSize: '11px',
                          color: '#8b949e',
                        }}
                      >
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                          // ACTIVE ({sessions.length})
                        </span>
                        <button
                          type="button"
                          onClick={handleNewChat}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--accent-color)',
                            fontSize: '11px',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 600,
                            cursor: 'pointer',
                            padding: '1px 4px',
                          }}
                          title="새 작업 추가"
                        >
                          + NEW
                        </button>
                      </div>
                      {sessions.length === 0 ? (
                        <div
                          className="task-item"
                          onClick={handleNewChat}
                          style={{ color: 'var(--text-muted)', fontStyle: 'italic', padding: '2px 0' }}
                        >
                          // no active tasks
                        </div>
                      ) : (
                        sessions.slice(0, 6).map((s) => (
                          <div
                            key={s.id}
                            className={`task-item ${activeSessionId === s.id ? 'active' : ''}`}
                            onClick={() => handleSelectSession(s.id)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              gap: '6px',
                              padding: '3px 6px',
                              borderRadius: '2px',
                              background: activeSessionId === s.id ? 'rgba(229, 169, 59, 0.12)' : 'transparent',
                              borderLeft: activeSessionId === s.id ? '2px solid var(--accent-color)' : '2px solid transparent',
                              color: activeSessionId === s.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                            }}
                            title={s.title || '작업'}
                          >
                            {editingSessionId === s.id ? (
                              <input
                                type="text"
                                className="session-title-edit-input"
                                value={editTitleText}
                                autoFocus
                                onChange={(e) => setEditTitleText(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleSaveRename(s.id);
                                  else if (e.key === 'Escape') setEditingSessionId(null);
                                }}
                                onBlur={() => handleSaveRename(s.id)}
                                onClick={(e) => e.stopPropagation()}
                              />
                            ) : (
                              <>
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                  {activeSessionId === s.id ? '▶ ' : '• '}
                                  {s.title || '새 대화'}
                                </span>
                                <div className="task-item-actions">
                                  <button
                                    type="button"
                                    className="rename-sub-btn"
                                    title="대화 제목 수정"
                                    aria-label={`${s.title || '대화'} 제목 수정`}
                                    onClick={(e) => handleStartRename(e, s)}
                                  >
                                    ✎
                                  </button>
                                  <button
                                    type="button"
                                    className="delete-sub-btn"
                                    title="대화 삭제"
                                    aria-label={`${s.title || '대화'} 삭제`}
                                    onClick={(e) => handleDeleteSession(e, s)}
                                  >
                                    ✕
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── Section: 최근 ─────────────────────────────────────── */}
        <div className="codex-section-container">
          <div className="codex-section-label">// RECENTS</div>
          <div className="codex-recents-list">
            {sessions.length === 0 ? (
              <div className="recent-link" onClick={handleNewChat}>
                // no recent threads
              </div>
            ) : (
              sessions.slice(0, 8).map(s => (
                <div
                  key={s.id}
                  className={`recent-link ${activeSessionId === s.id ? 'active' : ''}`}
                  onClick={() => handleSelectSession(s.id)}
                >
                  <span className="recent-status-dot" aria-hidden="true" style={{ background: activeSessionId === s.id ? 'var(--accent-color)' : 'var(--text-muted)' }} />
                  {editingSessionId === s.id ? (
                    <input
                      type="text"
                      className="session-title-edit-input"
                      value={editTitleText}
                      autoFocus
                      onChange={(e) => setEditTitleText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveRename(s.id);
                        else if (e.key === 'Escape') setEditingSessionId(null);
                      }}
                      onBlur={() => handleSaveRename(s.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <>
                      <span className="recent-title">{s.title || '대화'}</span>
                      <div className="recent-link-actions">
                        <button
                          type="button"
                          className="rename-sub-btn"
                          title="대화 제목 수정"
                          aria-label={`${s.title || '대화'} 제목 수정`}
                          onClick={(e) => handleStartRename(e, s)}
                        >
                          ✎
                        </button>
                        <button
                          type="button"
                          className="delete-sub-btn"
                          title="대화 삭제"
                          aria-label={`${s.title || '대화'} 삭제`}
                          onClick={(e) => handleDeleteSession(e, s)}
                        >
                          ✕
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ── Bottom User Profile Bar: Ssak-Ai Operator ──────────── */}
      <div className="codex-user-bottom-bar" style={{ borderTop: '1px solid var(--terminal-border)', background: 'var(--bg-secondary)', padding: '10px 14px' }}>
        <div className="user-profile-left">
          <div className="avatar-initial-circle" style={{ background: 'var(--terminal-border)', border: '1px solid var(--terminal-green)', color: 'var(--terminal-green)', fontFamily: 'var(--font-mono)' }}>
            MK
          </div>
          <span className="user-display-name" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
            mr.k // OPERATOR
          </span>
        </div>
        <div className="user-profile-right">
          <button
            type="button"
            className="voice-action-pill"
            onClick={() => addToast('음성 대화 모드가 준비되었습니다.', 'info')}
            title="음성 대화"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '10.5px', border: '1px solid var(--terminal-border)', background: 'var(--bg-tertiary)', color: 'var(--accent-color)' }}
          >
            <span className="sound-wave-icon">ılı</span>
            <span className="voice-text">VOICE</span>
          </button>
          <NavLink to="/settings" className="help-icon-link" title="도움말 및 설정" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            [?]
          </NavLink>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
