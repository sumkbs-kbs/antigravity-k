// @ts-nocheck
import React from 'react';
import { MarketplaceSkill, SearchResult, esc } from './types';
import SearchResultCard from './SearchResultCard';
import EmptyState from './EmptyState';

interface MarketplaceTabProps {
  skills: MarketplaceSkill[];
  recommended: SearchResult[];
  installedNames: string[];
  onRemove: (skillName: string) => void;
  onInstall: (pkgName: string) => void;
}

const MarketplaceTab: React.FC<MarketplaceTabProps> = ({
  skills,
  recommended,
  installedNames,
  onRemove,
  onInstall,
}) => {
  if (skills.length === 0) {
    return (
      <>
        <EmptyState
          icon="🏪"
          title="설치된 마켓 스킬이 없습니다."
          subtitle="아래 추천 스킬을 검색하여 설치할 수 있습니다."
        />
        {recommended.length > 0 && (
          <div style={{ marginTop: 24 }}>
            <h3 style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 12 }}>
              🔥 추천 스킬
            </h3>
            <div className="skills-grid">
              {recommended.map(s => (
                <SearchResultCard
                  key={s.name}
                  result={s}
                  installed={installedNames.includes(s.skill_name || s.name)}
                  onInstall={onInstall}
                />
              ))}
            </div>
          </div>
        )}
      </>
    );
  }

  const loadedCount = skills.filter(s => s.is_loaded).length;
  const mcpCount = skills.filter(s => s.mcp_server_id).length;

  return (
    <>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16 }}>
        <span className="status-badge active" style={{ fontSize: 12 }}>
          {skills.length} installed
        </span>
        <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          {loadedCount} loaded · {mcpCount} with MCP
        </span>
      </div>
      <div className="skills-grid">
        {skills.map(skill => (
          <div key={skill.name} className="glass-panel skill-card">
            <div className="skill-card-header">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 14 }}>🏪</span>
                  <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                    {esc(skill.name)}
                  </strong>
                </div>
              </div>
              <div style={{
                display: 'flex',
                gap: 4,
                flexShrink: 0,
                flexWrap: 'wrap',
                justifyContent: 'flex-end',
              }}>
                {skill.is_loaded
                  ? <span className="status-badge active" style={{ fontSize: 10 }}>✅ Loaded</span>
                  : <span className="status-badge pending" style={{ fontSize: 10 }}>⏳ Not loaded</span>}
                {skill.mcp_server_id && (
                  <span className="status-badge" style={{
                    fontSize: 10,
                    background: 'rgba(99,102,241,0.15)',
                    color: '#a5b4fc',
                  }}>
                    🔌 {esc(skill.mcp_server_id)}
                  </span>
                )}
              </div>
            </div>
            <div className="skill-card-meta" style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: 11,
              color: 'var(--text-muted)',
            }}>
              <span>📦 v{skill.version || 'unknown'}</span>
              <button
                className="glass-btn danger small"
                onClick={() => onRemove(skill.skill_name || skill.name)}
              >
                🗑️ Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
};

export default MarketplaceTab;
