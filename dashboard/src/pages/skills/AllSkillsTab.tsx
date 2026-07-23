import React from 'react';
import { Skill, esc } from './types';
import SkillCard from './SkillCard';
import EmptyState from './EmptyState';

interface AllSkillsTabProps {
  skills: Skill[];
}

const SOURCE_ORDER = ['global', 'local', 'market', 'unknown'] as const;

const SOURCE_META: Record<string, { icon: string; label: string; color: string }> = {
  global: { icon: '🌐', label: 'Global', color: '#60a5fa' },
  local: { icon: '📁', label: 'Local (.agent/skills)', color: '#34d399' },
  market: { icon: '🏪', label: 'Market (installed)', color: '#fbbf24' },
  unknown: { icon: '❓', label: 'Unknown', color: '#8b8fa3' },
};

const AllSkillsTab: React.FC<AllSkillsTabProps> = ({ skills }) => {
  if (skills.length === 0) {
    return (
      <EmptyState
        icon="🧰"
        title="로드된 스킬이 없습니다."
        subtitle=".agent/skills/ 디렉토리에 스킬이 없습니다."
      />
    );
  }

  return (
    <div>
      {SOURCE_ORDER.map(source => {
        const group = skills.filter(s => (s.source || 'unknown') === source);
        if (!group.length) return null;
        const meta = SOURCE_META[source] || SOURCE_META.unknown;

        return (
          <div key={source} className="skills-source-group">
            <div className="skills-source-header">
              <span style={{ fontSize: 18 }}>{meta.icon}</span>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: meta.color }}>
                {meta.label}
              </h3>
              <span className="skills-count" style={{
                background: 'rgba(255,255,255,0.08)',
                padding: '2px 8px',
                borderRadius: 10,
                fontSize: 11,
                color: 'var(--text-secondary)',
              }}>
                {group.length}
              </span>
            </div>
            <div className="skills-grid">
              {group.map(skill => (
                <SkillCard key={skill.id || skill.name} skill={skill} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default AllSkillsTab;
