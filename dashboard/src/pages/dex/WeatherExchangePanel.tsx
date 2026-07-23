/**
 * WeatherExchangePanel — Weather + Exchange rate panels (right column)
 * =====================================================================
 */

import React from 'react';
import { ExtractedWeather, ExtractedExchange } from './types';
import { GlassPanel, EmptyData } from './Common';

interface Props {
  weather: ExtractedWeather[];
  exchange: ExtractedExchange[];
}

const WeatherExchangePanel: React.FC<Props> = ({ weather, exchange }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Weather */}
      <GlassPanel title="☀️ 날씨 데이터" count={weather.length}>
        {weather.length > 0 ? (
          weather.map((w, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
            }}>
              <span style={{ fontSize: 20 }}>🌤️</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: 13 }}>
                  {w.location || '알 수 없음'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {w.temperature != null && `${w.temperature}°C`}
                  {w.humidity != null && ` | 습도 ${w.humidity}%`}
                  {w.condition && ` | ${w.condition}`}
                </div>
              </div>
            </div>
          ))
        ) : (
          <EmptyData msg="추출된 날씨 데이터가 없습니다" />
        )}
      </GlassPanel>

      {/* Exchange */}
      <GlassPanel title="💱 환율 데이터" count={exchange.length}>
        {exchange.length > 0 ? (
          exchange.map((e, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0' }}>
              <span style={{ fontSize: 18 }}>💲</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: 13 }}>{e.currency_pair}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {e.rate != null && e.rate.toLocaleString()}
                  {e.change_percent != null && (
                    <span style={{ color: e.change_percent >= 0 ? '#10b981' : '#ef4444' }}>
                      {' '}{e.change_percent >= 0 ? '+' : ''}{e.change_percent.toFixed(2)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : (
          <EmptyData msg="추출된 환율 데이터가 없습니다" />
        )}
      </GlassPanel>
    </div>
  );
};

export default WeatherExchangePanel;
