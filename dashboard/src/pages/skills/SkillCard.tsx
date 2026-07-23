import React from 'react';
import { Skill, esc } from './types';

interface SkillCardProps {
  skill: Skill;
}

const SOURCE_META: Record<string, { icon: string; color: string }> = {
  global: { icon: '🌐', color: '#60a5fa' },
  local: { icon: '📁', color: '#34d399' },
  market: { icon: '🏪', color: '#fbbf24' },
  unknown: { icon: '❓', color: '#8b8fa3' },
};

const SkillCard: React.FC<SkillCardProps> = ({ skill }) => {
  const source = skill.source || 'unknown';
  const meta = SOURCE_META[source] || SOURCE_META.unknown;

  return (
    <div className="glass-panel skill-card">
      <div className="skill-card-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ fontSize: 14 }}>{meta.icon}</span>
            <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>{esc(skill.name || skill.id || 'Unknown')}</strong>
          </div>
          {skill.description && (
            <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
              {skill.description}
            </p>
          )}
        </div>
        <span style={{
          fontSize: 10,
          padding: '2px 8px',
          borderRadius: 10,
          fontWeight: 600,
          background: `${meta.color}18`,
          color: meta.color,
          border: `1px solid ${meta.color}30`,
        }}>
          {source}
        </span>
      </div>
      <div className="skill-card-meta" style={{
        display: 'flex',
        gap: 12,
        fontSize: 11,
        color: 'var(--text-muted)',
        alignItems: 'center',
      }}>
        {skill.version && <span>📦 v{esc(skill.version)}</span>}
        {skill.id && (
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
            ID: {esc(skill.id)}
          </span>
        )}
      </div>
    </div>
  );
};

export default SkillCard;
