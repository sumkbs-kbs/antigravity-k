/**
 * BottomPanels — Dates + LLM Log panels (bottom row)
 * ====================================================
 */

import React from 'react';
import { ExtractionData } from './types';
import { GlassPanel, EmptyData } from './Common';

interface Props {
  result: ExtractionData;
}

const BottomPanels: React.FC<Props> = ({ result }) => {
  const dates = result.extracted?.dates_found || [];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16, marginTop: 16 }}>
      {/* Dates */}
      <GlassPanel title="📅 추출된 날짜" count={dates.length}>
        {dates.length > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {dates.map((d, i) => (
              <span key={i} style={{
                padding: '4px 8px', borderRadius: 6,
                background: 'rgba(124,106,239,0.08)',
                color: 'var(--accent-color)', fontSize: 12,
                border: '1px solid rgba(124,106,239,0.2)',
              }}>
                📌 {d}
              </span>
            ))}
          </div>
        ) : (
          <EmptyData msg="추출된 날짜가 없습니다" />
        )}
      </GlassPanel>

      {/* LLM Log */}
      <GlassPanel title="🤖 LLM 포맷 출력" subtitle="format_for_llm()">
        {result.extraction_log ? (
          <pre style={{
            margin: 0, fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12, lineHeight: 1.6,
            color: 'var(--text-secondary)', whiteSpace: 'pre-wrap',
          }}>
            {result.extraction_log}
          </pre>
        ) : (
          <EmptyData msg="추출된 데이터가 없습니다" />
        )}
      </GlassPanel>
    </div>
  );
};

export default BottomPanels;
