/**
 * PipelineStatus — Pipeline steps visualization + summary badges
 * ===============================================================
 */
// @ts-nocheck


import React from 'react';
import { ExtractionData, METRICS_BASE, STATUS_ICONS, PipelineStatusType } from './types';
import { StatBadge } from './Common';

interface Props {
  result: ExtractionData;
}

function getStepStatus(result: ExtractionData, stepId: string): PipelineStatusType {
  const sp = result.extracted?.stock_prices || [];
  const weather = result.extracted?.weather || [];
  const exchange = result.extracted?.exchange_rates || [];
  const dates = result.extracted?.dates_found || [];

  switch (stepId) {
    case 'search':  return result.search_length > 0 ? 'success' : 'fail';
    case 'top1_json': return result.has_top1_json ? 'success' : 'fail';
    case 'ticker':   return sp.some(p => p.ticker) ? 'success' : sp.length > 0 ? 'partial' : 'idle';
    case 'manwon':   return sp.some(p => p.close_price) ? 'success' : sp.length > 0 ? 'partial' : 'idle';
    case 'extract':  return (sp.length + weather.length + exchange.length + dates.length) > 0 ? 'success' : 'idle';
    default:         return 'idle';
  }
}

const PipelineStatus: React.FC<Props> = ({ result }) => {
  const sp = result.extracted?.stock_prices || [];
  const weather = result.extracted?.weather || [];
  const exchange = result.extracted?.exchange_rates || [];
  const dates = result.extracted?.dates_found || [];

  return (
    <>
      {/* Pipeline Steps */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap',
        padding: '16px 20px', marginBottom: 20,
        background: 'rgba(0,0,0,0.3)', borderRadius: 12,
        border: '1px solid var(--glass-border)',
      }}>
        {METRICS_BASE.map((s, i) => {
          const st = getStepStatus(result, s.id);
          const bgColor = st === 'success' ? 'rgba(16,185,129,0.12)'
            : st === 'fail' ? 'rgba(239,68,68,0.12)'
            : st === 'partial' ? 'rgba(251,191,36,0.12)' : 'transparent';
          const fgColor = st === 'success' ? '#10b981'
            : st === 'fail' ? '#ef4444' : 'var(--text-secondary)';

          return (
            <React.Fragment key={s.id}>
              <span style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 8px', borderRadius: 6,
                background: bgColor, fontSize: 11, color: fgColor,
                cursor: 'help',
              }} title={s.desc}>
                {STATUS_ICONS[st]} {s.icon} {s.label}
              </span>
              {i < METRICS_BASE.length - 1 && (
                <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>→</span>
              )}
            </React.Fragment>
          );
        })}
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
          {result.search_length.toLocaleString()} chars | {result.query}
        </span>
      </div>

      {/* Summary Badges */}
      <div style={{
        display: 'flex', gap: 12, flexWrap: 'wrap',
        padding: '12px 16px', marginBottom: 16,
        background: 'rgba(0,0,0,0.2)', borderRadius: 10,
        border: '1px solid var(--glass-border)', alignItems: 'center',
      }}>
        <span style={{ fontSize: 12 }}>📐 추출 결과:</span>
        <StatBadge icon="📈" text={`주식 ${sp.length}건`} color="rgba(16,185,129,0.1)" />
        <StatBadge icon="☀️" text={`날씨 ${weather.length}건`} color="rgba(251,191,36,0.1)" />
        <StatBadge icon="💱" text={`환율 ${exchange.length}건`} color="rgba(124,106,239,0.1)" />
        <StatBadge icon="📅" text={`날짜 ${dates.length}건`} color="rgba(59,130,246,0.1)" />
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
          {result.has_top1_json ? '📋 TOP1 JSON ✅' : '📋 TOP1 JSON ❌'}
        </span>
      </div>
    </>
  );
};

export default PipelineStatus;
