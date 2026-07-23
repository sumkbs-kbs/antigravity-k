/**
 * SkillsPage — Skills Browser
 * =============================
 * Tab-based router for All Skills, Marketplace, Search npm, MCP Servers.
 * Each tab is extracted as a separate sub-component in ./skills/.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useUiStore } from '../stores/uiStore';
import { Skill, MarketplaceSkill, SearchResult, MCPServer } from './skills/types';
import AllSkillsTab from './skills/AllSkillsTab';
import MarketplaceTab from './skills/MarketplaceTab';
import SearchTab from './skills/SearchTab';
import MCPTab from './skills/MCPTab';
import PublishTab from './skills/PublishTab';

type Tab = 'all' | 'marketplace' | 'search' | 'mcp' | 'publish';
type CountKey = 'all' | 'market' | 'mcp';

const SkillsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('all');
  const [skills, setSkills] = useState<Skill[]>([]);
  const [marketSkills, setMarketSkills] = useState<MarketplaceSkill[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [mcpServers, setMCPservers] = useState<MCPServer[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [silentLoading, setSilentLoading] = useState(false);
  const skillsCountRef = useRef(0);

  const tabs: { id: Tab; icon: string; label: string; countKey?: CountKey }[] = [
    { id: 'all', icon: '🧰', label: 'All Skills', countKey: 'all' },
    { id: 'marketplace', icon: '🏪', label: 'Marketplace', countKey: 'market' },
    { id: 'search', icon: '🔍', label: 'Search npm' },
    { id: 'publish', icon: '📦', label: 'Publish' },
    { id: 'mcp', icon: '🔌', label: 'MCP Servers', countKey: 'mcp' },
  ];

  const counts: Record<CountKey, number> = {
    all: skills.length,
    market: marketSkills.length,
    mcp: mcpServers.length,
  };

  const loadTab = useCallback(async (tab: Tab) => {
    setLoading(true);
    try {
      switch (tab) {
        case 'all': {
          const res = await fetch('/api/system/skills');
          const data = await res.json();
          setSkills(data.skills || []);
          break;
        }
        case 'marketplace': {
          const res = await fetch('/api/system/skills/installed');
          const data = await res.json();
          setMarketSkills(data.installed || []);
          if (!data.installed?.length) {
            try {
              const searchRes = await fetch('/api/system/skills/search?q=skill&limit=10');
              const searchData = await searchRes.json();
              if (searchData.ok) setSearchResults(searchData.results || []);
            } catch { /* ignore */ }
          }
          break;
        }
        case 'mcp': {
          const res = await fetch('/api/system/skills/mcp');
          const data = await res.json();
          setMCPservers(data.servers || []);
          break;
        }
      }
    } catch (err) {
      console.error('Skills load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTab(activeTab); }, [activeTab, loadTab]);

  // Auto-discovery polling: silently refresh 'all' tab every 20s
  useEffect(() => {
    const interval = setInterval(async () => {
      if (activeTab !== 'all') return;
      setSilentLoading(true);
      try {
        const res = await fetch('/api/system/skills');
        const data = await res.json();
        const newSkills = data.skills || [];
        if (skillsCountRef.current > 0 && newSkills.length !== skillsCountRef.current) {
          setSilentLoading(false);
          setSkills(newSkills);
          skillsCountRef.current = newSkills.length;
          useUiStore.getState().addToast(`🔄 새 스킬 감지: ${newSkills.length}개`, 'info');
          return;
        }
        skillsCountRef.current = newSkills.length;
        setSkills(newSkills);
      } catch { /* ignore */ }
      setSilentLoading(false);
    }, 20000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setActiveTab('search');
    setLoading(true);
    try {
      const res = await fetch(`/api/system/skills/search?q=${encodeURIComponent(searchQuery)}&limit=20`);
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch {
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  const doInstall = useCallback(async (pkgName: string) => {
    try {
      const res = await fetch('/api/system/skills/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package_name: pkgName }),
      });
      const data = await res.json();
      if (data.ok) {
        useUiStore.getState().addToast(`✅ ${pkgName} installed`, 'success');
        loadTab('marketplace');
      }
    } catch { /* ignore */ }
  }, [loadTab]);

  const doRemove = useCallback(async (skillName: string) => {
    if (!confirm(`"${skillName}" 스킬을 제거하시겠습니까?`)) return;
    try {
      const res = await fetch('/api/system/skills/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_name: skillName }),
      });
      if (res.ok) {
        useUiStore.getState().addToast(`🗑️ ${skillName} removed`, 'success');
        loadTab('marketplace');
      }
    } catch { /* ignore */ }
  }, [loadTab]);

  const installedNames = marketSkills.map(s => s.skill_name || s.name);

  return (
    <div className="page-container" style={{ maxWidth: 1100 }}>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}>
          <div>
            <h2>Skills Browser <span>Skill Management</span></h2>
            <p className="page-subtitle">
              로드된 스킬, 마켓플레이스 설치 현황, npm 검색, MCP 서버를 한눈에 확인합니다.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {silentLoading && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>🔄 확인 중...</span>
            )}
            <button className="glass-btn primary" onClick={() => loadTab(activeTab)} style={{ gap: 6 }}>
              <span>🔄</span> 새로고침
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="skills-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`skills-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.icon} {tab.label}
            {tab.countKey && <span className="skills-count">{(counts as any)[tab.countKey] || 0}</span>}
          </button>
        ))}
      </div>

      {/* Search bar (visible on search tab) */}
      {activeTab === 'search' && (
        <div className="skills-search-bar" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, maxWidth: 600 }}>
            <input
              type="text"
              className="glass-input"
              placeholder="npm에서 @antigravity-k/skill-* 패키지 검색..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              style={{
                flex: 1,
                padding: '10px 14px',
                fontSize: 14,
                background: 'rgba(0,0,0,0.2)',
                border: '1px solid var(--glass-border)',
                color: '#fff',
                borderRadius: 6,
              }}
            />
            <button className="glass-btn primary" onClick={handleSearch} style={{ padding: '8px 16px' }}>
              검색
            </button>
          </div>
        </div>
      )}

      {/* Tab Content */}
      {loading ? (
        <div className="skills-loading">🔄 데이터를 불러오는 중...</div>
      ) : (
        <>
          {activeTab === 'all' && <AllSkillsTab skills={skills} />}
          {activeTab === 'marketplace' && (
            <MarketplaceTab
              skills={marketSkills}
              recommended={searchResults}
              installedNames={installedNames}
              onRemove={doRemove}
              onInstall={doInstall}
            />
          )}
          {activeTab === 'search' && (
            <SearchTab
              results={searchResults}
              installedNames={installedNames}
              onQueryChange={setSearchQuery}
              onSearch={handleSearch}
              onInstall={doInstall}
            />
          )}
          {activeTab === 'publish' && <PublishTab />}
          {activeTab === 'mcp' && <MCPTab servers={mcpServers} />}
        </>
      )}
    </div>
  );
};

export default SkillsPage;
