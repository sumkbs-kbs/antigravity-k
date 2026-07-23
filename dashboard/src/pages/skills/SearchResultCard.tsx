import React from 'react';
import { SearchResult, esc } from './types';

interface SearchResultCardProps {
  result: SearchResult;
  installed: boolean;
  onInstall: (pkgName: string) => void;
}

const SearchResultCard: React.FC<SearchResultCardProps> = ({ result, installed, onInstall }) => {
  const keywords = Array.isArray(result.keywords) ? result.keywords.slice(0, 4) : [];

  return (
    <div className="glass-panel skill-card">
      <div className="skill-card-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ fontSize: 14 }}>📦</span>
            <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>
              {esc(result.skill_name || result.name)}
            </strong>
            <span style={{
              fontSize: 11,
              color: 'var(--text-muted)',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              v{esc(result.version)}
            </span>
          </div>
          {result.description && (
            <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
              {result.description}
            </p>
          )}
        </div>
        {installed ? (
          <button className="glass-btn small" disabled style={{ fontSize: 10, opacity: 0.5 }}>
            ✅ Installed
          </button>
        ) : (
          <button className="glass-btn primary small" onClick={() => onInstall(result.name)} style={{ fontSize: 10 }}>
            📦 Install
          </button>
        )}
      </div>
      <div className="skill-card-meta" style={{
        display: 'flex',
        gap: 8,
        fontSize: 11,
        color: 'var(--text-muted)',
        alignItems: 'center',
        marginTop: 8,
        flexWrap: 'wrap',
      }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
          {esc(result.name)}
        </span>
        {result.publisher && <span>👤 {esc(result.publisher)}</span>}
      </div>
      {keywords.length > 0 && (
        <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
          {keywords.map((k, i) => (
            <span key={i} style={{
              fontSize: 9,
              padding: '1px 6px',
              background: 'rgba(255,255,255,0.05)',
              borderRadius: 4,
              color: 'var(--text-muted)',
            }}>
              {k}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default SearchResultCard;
