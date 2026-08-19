/**
 * Sidebar — Navigation and system status
 * =======================================
 * Redesigned with unsloth.ai inspired aesthetics: clean, spacious, developer-first.
 */

import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';

const MODE_STYLES: Record<string, { icon: string; label: string; color: string; bg: string }> = {
  plan: { icon: '📋', label: 'PLAN', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.12)' },
  build: { icon: '🔨', label: 'BUILD', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' },
  interactive: { icon: '💬', label: 'INTERACTIVE', color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.12)' },
};

const NAV_ITEMS = [
  { path: '/chat', icon: '💬', label: 'AI 채팅' },
  { path: '/wiki', icon: '📚', label: 'LLM Wiki' },
  { path: '/agent', icon: '🤖', label: '에이전트' },
  { path: '/skills', icon: '🧰', label: '스킬' },
  { path: '/data-extraction', icon: '🔬', label: '데이터 추출' },
  { path: '/git', icon: '🐙', label: 'Git' },
  { path: '/history', icon: '📜', label: '히스토리' },
  { path: '/plugins', icon: '🔌', label: '플러그인' },
  { path: '/mutation', icon: '🧬', label: 'Mutation' },
  { path: '/settings', icon: '⚙️', label: '설정' },
];

const ProviderStatusPanel: React.FC = () => {
  const { systemStatus } = useUiStore();
  const { backends } = systemStatus;

  const knownProviders = [
    { name: 'Ollama', key: 'ollama', icon: '🏠' },
    { name: 'OpenRouter', key: 'openrouter', icon: '🌐' },
    { name: 'NIM', key: 'nim', icon: '🟢' },
    { name: 'OpenAI', key: 'openai', icon: '🔵' },
    { name: 'Gemini', key: 'gemini', icon: '✨' },
  ];

  const activeModels = Array.isArray(backends) ? backends : Object.values(backends || {});
  const activeProviders = new Set<string>();

  activeModels.forEach((m: any) => {
    const name = (m.name || m.model || '').toLowerCase();
    if (name.includes('ollama') || name.includes(':latest')) activeProviders.add('ollama');
    if (name.includes('openrouter') || (name.includes('/') && !name.startsWith('gpt'))) activeProviders.add('openrouter');
    if (name.startsWith('deepseek-ai/') || name.startsWith('meta/') || name.startsWith('nvidia/')) activeProviders.add('nim');
    if (name.startsWith('gpt') || name.startsWith('o3')) activeProviders.add('openai');
    if (name.startsWith('gemini')) activeProviders.add('gemini');
  });

  return (
    <div className="provider-status-panel">
      {knownProviders.map(p => (
        <span
          key={p.key}
          className={`provider-badge ${activeProviders.has(p.key) ? 'active' : ''}`}
          title={p.name}
        >
          <span className="dot" />
          {p.icon} {p.name}
        </span>
      ))}
    </div>
  );
};

const ModeIndicator: React.FC = () => {
  const { mode, setMode, addToast } = useUiStore();
  const style = MODE_STYLES[mode] || MODE_STYLES.interactive;
  const modes = ['interactive', 'plan', 'build'];

  const handleClick = async () => {
    const currentIdx = modes.indexOf(mode);
    const nextMode = modes[(currentIdx + 1) % modes.length] as keyof typeof MODE_STYLES;
    const pin = localStorage.getItem('ag_access_pin') || '0000';

    try {
      const res = await fetch('/api/system/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Pin': pin },
        body: JSON.stringify({ mode: nextMode, reason: '대시보드 클릭' }),
      });
      const data = await res.json();
      if (data.ok) {
        setMode(nextMode as any);
        addToast(`모드 전환: ${nextMode.toUpperCase()}`, 'success');
      } else {
        addToast(`모드 전환 실패: ${data.error || ''}`, 'error');
      }
    } catch (err: any) {
      addToast(`서버 오류: ${err.message}`, 'error');
    }
  };

  return (
    <div
      className="mode-indicator"
      onClick={handleClick}
      role="button"
      tabIndex={0}
      title={`${style.label} 모드 — 클릭하여 전환`}
    >
      <span className="mode-icon" aria-hidden="true">{style.icon}</span>
      <span className="mode-label" style={{ color: style.color }}>{style.label}</span>
      <span
        className="mode-dot"
        style={{ background: style.color, boxShadow: `0 0 8px ${style.color}` }}
        aria-hidden="true"
      />
    </div>
  );
};

interface SidebarProps {
  toggleTerminal?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ toggleTerminal }) => {
  const { systemStatus, setCommandPaletteVisible, addToast } = useUiStore();
  const location = useLocation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [projectName, setProjectName] = useState('기본 프로젝트');

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const handleRestart = async () => {
    if (!confirm('정말로 서버를 재시작하시겠습니까?')) return;
    try {
      await fetch('/api/system/restart', { method: 'POST' });
      addToast('🔄 서버 재시작 중...', 'info');
      setTimeout(() => window.location.reload(), 3000);
    } catch (err: any) {
      addToast(`재시작 실패: ${err.message}`, 'error');
    }
  };

  const isActive = (path: string) => {
    if (path === '/chat') return location.pathname === '/' || location.pathname === '/chat';
    return location.pathname === path;
  };

  return (
    <aside className="sidebar" role="navigation" aria-label="메인 사이드바">
      {/* ── Header: Logo & Project ──────────────────────────────── */}
      <div className="sidebar-header">
        <div className="logo-group">
          <span className="logo-icon" aria-hidden="true">🚀</span>
          <span className="logo-text">Antigravity-K</span>
        </div>
        <div className="sidebar-divider" />

        <div className="project-selector" ref={dropdownRef}>
          <button
            className="project-trigger"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            aria-label="프로젝트 선택"
            aria-expanded={dropdownOpen}
          >
            <span className="project-icon" aria-hidden="true">📁</span>
            <span className="project-name">{projectName}</span>
            <span className="project-chevron" aria-hidden="true">
              {dropdownOpen ? '▲' : '▼'}
            </span>
          </button>
          {dropdownOpen && (
            <div className="project-dropdown" role="menu">
              <div className="project-dropdown-item" role="menuitem">
                📁 기본 프로젝트
              </div>
              <div className="project-dropdown-divider" />
              <div className="project-dropdown-item" role="menuitem">
                + 새 프로젝트
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Main Navigation ─────────────────────────────────────── */}
      <nav className="sidebar-nav" aria-label="메인 네비게이션">
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive: active }) =>
              `nav-item ${active || isActive(item.path) ? 'active' : ''}`
            }
            aria-label={item.label}
          >
            <span className="nav-icon" aria-hidden="true">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* ── Footer: System Status & Actions ────────────────────── */}
      <div className="sidebar-footer">
        <div className="sidebar-section">
          <span className="sidebar-section-label">PROVIDERS</span>
          <ProviderStatusPanel />
        </div>

        <div className="sidebar-section">
          <span className="sidebar-section-label">MODE</span>
          <ModeIndicator />
        </div>

        <div className="sidebar-section">
          <span className="sidebar-section-label">SYSTEM</span>
          <div className="system-status">
            <div className="status-row">
              <span className={`status-dot ${systemStatus.healthy ? 'online' : 'offline'}`} aria-hidden="true" />
              <span className="status-text">
                {systemStatus.healthy ? '엔진 활성' : '연결 확인 중...'}
              </span>
            </div>
            {systemStatus.healthy && (
              <div className="system-metrics">
                <div className="metric">
                  <div className="metric-head">
                    <span className="metric-label">RAM</span>
                    <span className="metric-value">{systemStatus.memoryMb}%</span>
                 </div>
                  <div className="metric-bar">
                    <span
                      className="metric-bar-fill"
                      data-level={systemStatus.memoryMb > 80 ? 'high' : systemStatus.memoryMb > 50 ? 'mid' : 'low'}
                      style={{ width: `${Math.min(100, Math.max(0, systemStatus.memoryMb))}%` }}
                    />
                 </div>
               </div>
                <div className="metric">
                  <div className="metric-head">
                    <span className="metric-label">CPU</span>
                    <span className="metric-value">{systemStatus.cpuPercent}%</span>
                 </div>
                  <div className="metric-bar">
                    <span
                      className="metric-bar-fill"
                      data-level={systemStatus.cpuPercent > 80 ? 'high' : systemStatus.cpuPercent > 50 ? 'mid' : 'low'}
                      style={{ width: `${Math.min(100, Math.max(0, systemStatus.cpuPercent))}%` }}
                    />
                 </div>
               </div>
                <div className="metric metric-inline">
                  <span className="metric-label">Tokens</span>
                  <span className="metric-value metric-value-mono">{systemStatus.totalTokens.toLocaleString()}</span>
               </div>
             </div>
            )}
          </div>
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-actions">
          <button
            className="action-btn"
            onClick={() => setCommandPaletteVisible(true)}
            aria-label="명령 팔레트 열기 (Cmd+K)"
          >
            <span className="action-icon">🔍</span>
            <span className="action-label">명령 팔레트</span>
            <kbd className="action-shortcut">Cmd+K</kbd>
          </button>
          <button
            className="action-btn"
            onClick={() => toggleTerminal?.()}
            aria-label="터미널 토글 (Cmd+`)"
          >
            <span className="action-icon">💻</span>
            <span className="action-label">터미널</span>
            <kbd className="action-shortcut">Cmd+`</kbd>
          </button>
          <button
            className="action-btn action-btn-danger"
            onClick={handleRestart}
            aria-label="서버 재시작"
          >
            <span className="action-icon">🔄</span>
            <span className="action-label">재시작</span>
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
