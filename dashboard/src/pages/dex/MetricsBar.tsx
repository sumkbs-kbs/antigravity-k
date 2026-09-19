/**
 * MetricsBar — Top metrics display bar
 * ======================================
 */

import React from 'react';
import { MetricsData } from './types';
import { MetricItem } from './Common';

interface Props {
  metrics: MetricsData | null;
}

const MetricsBar: React.FC<Props> = ({ metrics }) => {
  return (
    <div className="dex-metrics-bar">
      {metrics ? (
        <>
          <MetricItem icon="📊" value={metrics.total_calls?.toLocaleString() || '0'} label="전체 호출" />
          <MetricItem icon="🎯" value={`${metrics.success_rates?.overall || 0}%`} label="정확도"
            color={metrics.success_rates?.overall && metrics.success_rates.overall >= 80 ? '#10b981' : '#f59e0b'} />
          <MetricItem icon="📈" value={`${metrics.stock_success || 0}/${metrics.stock_attempts || 0}`} label={`주식 ${metrics.success_rates?.stock || 0}%`} />
          <MetricItem icon="☀️" value={`${metrics.weather_success || 0}/${metrics.weather_attempts || 0}`} label={`날씨 ${metrics.success_rates?.weather || 0}%`} />
          <MetricItem icon="💱" value={`${metrics.exchange_success || 0}/${metrics.exchange_attempts || 0}`} label={`환율 ${metrics.success_rates?.exchange || 0}%`} />
          <MetricItem icon="🛡️" value={String(metrics.speculative_filtered || 0)} label="필터링" />
        </>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)' }}>
          <span>📡 메트릭 로딩 중...</span>
          <span className="dex-spinner-mini" style={{
            display: 'inline-block', width: 12, height: 12,
            border: '2px solid var(--glass-border)', borderTopColor: 'var(--accent-color)',
            borderRadius: '50%', animation: 'dex-spin 0.8s linear infinite',
          }} />
        </div>
      )}
    </div>
  );
};

export default MetricsBar;
