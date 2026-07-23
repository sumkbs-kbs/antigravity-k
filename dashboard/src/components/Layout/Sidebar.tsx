/**
 * Sidebar — Navigation and system status
 * =======================================
 * Ported from Vanilla JS. Uses React Router NavLink for navigation.
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
      className="flex items-center gap-sm px-sm py-xs rounded-lg cursor-pointer"
      style={{
        fontSize: 12, fontWeight: 600, transition: 'all 0.3s ease',
        background: style.bg, border: `1px solid ${style.color}`,
      }}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      title={`${style.label} 모드`}
    >
      <span style={{ fontSize: 16 }}>{style.icon}</span>
      <span className="flex-1" style={{ color: style.color }}>{style.label}</span>
      <span
        style={{
          width: 8, height: 8, borderRadius: '50%',
          background: style.color, boxShadow: `0 0 6px ${style.color}`,
        }}
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
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="flex items-center gap-sm">
          <span className="logo-icon">🚀</span>
          <span className="version-badge">v0.2.0</span>
        </div>
        <div className="logo">
          <span className="logo-text">Antigravity-K</span>
        </div>

        <div className="relative" ref={dropdownRef}>
          <div
            className="flex items-center gap-xs px-md py-xs rounded-lg cursor-pointer"
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.08)',
              fontSize: 12,
            }}
            onClick={() => setDropdownOpen(!dropdownOpen)}
            role="button"
            tabIndex={0}
            aria-label="프로젝트 선택"
          >
            <span style={{ fontSize: 14 }}>📂</span>
            <span className="flex-1 truncate text-secondary" style={{ fontSize: 12 }}>{projectName}</span>
            <span className="text-muted" style={{ fontSize: 10 }}>▼</span>
          </div>
        </div>
      </div>

      {/* Navigation with React Router NavLink */}
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

      {/* Footer */}
      <div className="flex flex-col gap-sm" style={{ borderTop: '1px solid var(--glass-border)', paddingTop: 12 }}>
        <ProviderStatusPanel />
        <ModeIndicator />

        <div className="flex items-center gap-sm" style={{ fontSize: 12 }}>
          <span className={`status-dot ${systemStatus.healthy ? 'online' : 'offline'}`} />
          <span className="text-secondary">
            {systemStatus.healthy ? '엔진 활성' : '연결 확인 중...'}
          </span>
        </div>

        {systemStatus.healthy && (
          <div className="text-xs text-secondary">
            RAM: {systemStatus.memoryMb}% | CPU: {systemStatus.cpuPercent}% | Tokens: {systemStatus.totalTokens.toLocaleString()}
          </div>
        )}

        <button
          className="icon-btn cursor-pointer"
          style={{ textAlign: 'left', padding: '6px 10px', fontSize: 12 }}
          onClick={() => setCommandPaletteVisible(true)}
          aria-label="명령 팔레트 열기 (Cmd+K)"
        >
          🔎 명령 팔레트
        </button>

        <button
          className="icon-btn cursor-pointer"
          style={{ textAlign: 'left', padding: '6px 10px', fontSize: 12 }}
          onClick={() => toggleTerminal?.()}
          aria-label="터미널 토글 (Cmd+`)"
        >
          💻 터미널
        </button>

        <button
          className="icon-btn cursor-pointer"
          style={{ textAlign: 'left', padding: '6px 10px', fontSize: 12 }}
          onClick={handleRestart}
          aria-label="서버 재시작"
        >
          🔄 서버 재시작
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
