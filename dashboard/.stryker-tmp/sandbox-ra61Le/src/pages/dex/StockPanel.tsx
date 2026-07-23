/**
 * StockPanel — Stock data cards panel
 * =====================================
 */
// @ts-nocheck


import React from 'react';
import { ExtractedStock } from './types';
import { GlassPanel, EmptyData, StatBox } from './Common';

interface Props {
  stocks: ExtractedStock[];
}

const StockPanel: React.FC<Props> = ({ stocks }) => {
  return (
    <GlassPanel title="📈 주식 데이터" count={stocks.length}>
      {stocks.length > 0 ? (
        stocks.map((s, i) => (
          <div key={i} style={{
            padding: 12, borderRadius: 8,
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            marginBottom: 8,
          }}>
            {/* Name + Ticker */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 15, fontWeight: 600, flex: 1 }}>
                {s.name || '(이름 없음)'}
              </span>
              {s.ticker && (
                <span style={{
                  padding: '2px 6px', borderRadius: 4,
                  background: 'rgba(124,106,239,0.1)', color: 'var(--accent-color)',
                  fontSize: 11, fontWeight: 500,
                }}>
                  {s.ticker}
                </span>
              )}
            </div>

            {/* Stats */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12 }}>
              {s.close_price != null && (
                <StatBox label="종가" value={`₩${s.close_price.toLocaleString()}`} bold />
              )}
              {s.open_price != null && (
                <StatBox label="시가" value={`₩${s.open_price.toLocaleString()}`} />
              )}
              {s.high_price != null && (
                <StatBox label="고가" value={`₩${s.high_price.toLocaleString()}`} />
              )}
              {s.low_price != null && (
                <StatBox label="저가" value={`₩${s.low_price.toLocaleString()}`} />
              )}
              {s.change_percent != null && (
                <StatBox
                  label="등락률"
                  value={`${s.change_percent >= 0 ? '+' : ''}${s.change_percent.toFixed(2)}%`}
                  color={s.change_percent >= 0 ? '#10b981' : '#ef4444'}
                />
              )}
            </div>
          </div>
        ))
      ) : (
        <EmptyData msg="추출된 주식 데이터가 없습니다" />
      )}
    </GlassPanel>
  );
};

export default StockPanel;
