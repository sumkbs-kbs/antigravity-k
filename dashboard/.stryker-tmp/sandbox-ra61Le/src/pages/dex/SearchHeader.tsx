/**
 * SearchHeader — Search bar + quick chips
 * =========================================
 */
// @ts-nocheck


import React from 'react';

const QUERY_CHIPS = [
  '한화에어로스페이스 주가 알려줘',
  '삼성전자 주가 알려줘',
  '서울 날씨 알려줘',
  '원달러 환율 알려줘',
];

interface Props {
  query: string;
  searching: boolean;
  onQueryChange: (q: string) => void;
  onSearch: () => void;
}

const SearchHeader: React.FC<Props> = ({ query, searching, onQueryChange, onSearch }) => {
  return (
    <div className="dex-header" style={{ padding: '24px 32px 16px', borderBottom: '1px solid var(--glass-border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <span style={{ fontSize: 28 }}>🔬</span>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>데이터 추출 대시보드</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
            검색 결과에서 구조화된 데이터를 자동 추출하여 시각화합니다
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="dex-search-bar" style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <input
            type="text"
            value={query}
            onChange={e => onQueryChange(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onSearch()}
            placeholder="검색어를 입력하세요 (예: 한화에어로스페이스 주가 알려줘)"
            style={{
              width: '100%', padding: '12px 14px 12px 40px',
              background: 'rgba(0,0,0,0.4)', border: '1px solid var(--glass-border)',
              borderRadius: 10, color: 'var(--text-primary)', fontSize: 14,
              outline: 'none', boxSizing: 'border-box',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--accent-color)'}
            onBlur={e => e.target.style.borderColor = 'var(--glass-border)'}
          />
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 16, opacity: 0.5 }}>
            🔎
          </span>
        </div>
        <button
          className="glow-btn"
          onClick={onSearch}
          disabled={searching}
          style={{
            padding: '12px 24px', borderRadius: 10, whiteSpace: 'nowrap',
            background: 'linear-gradient(135deg,var(--accent-color),#8b5cf6)',
            border: 'none', color: 'white', cursor: 'pointer',
            opacity: searching ? 0.6 : 1,
          }}
        >
          {searching ? '⏳ 검색 중...' : '🔎 검색 및 추출'}
        </button>
      </div>

      {/* Quick chips */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
        {QUERY_CHIPS.map(q => (
          <span
            key={q}
            className="dex-chip"
            onClick={() => onQueryChange(q)}
            style={{
              padding: '4px 10px', borderRadius: 6,
              background: 'rgba(124,106,239,0.08)', color: 'var(--text-secondary)',
              fontSize: 11, cursor: 'pointer', border: '1px solid transparent',
              transition: 'all 0.15s',
            }}
          >
            {q}
          </span>
        ))}
      </div>
    </div>
  );
};

export default SearchHeader;
