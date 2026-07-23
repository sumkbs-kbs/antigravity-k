/**
 * GlassPanel — Glass-morphism panel with title header + body
 * ===========================================================
 * Two variants:
 * - 'card' (default): inner header with border-bottom + inner body, rgba(0,0,0,0.25) bg
 *   Used by: DataExtractionPage (StockPanel, WeatherPanel, etc.)
 * - 'section': glass-panel CSS class + 24px padding + h3 title
 *   Used by: SettingsPage (API Keys, Model, Search Engine, etc.)
 */

import React from 'react';

interface Props {
  title: string;
  count?: number;
  subtitle?: string;
  children: React.ReactNode;
  variant?: 'card' | 'section';
  style?: React.CSSProperties;
  className?: string;
}

const GlassPanel: React.FC<Props> = ({ title, count, subtitle, children, variant = 'card', style, className }) => {
  // ─── Section variant: CSS glass-panel class + h3 + 24px padding ───
  if (variant === 'section') {
    return (
      <div className={`glass-panel${className ? ' ' + className : ''}`} style={{ padding: 24, ...style }}>
        <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>{title}</span>
        </h3>
        {children}
      </div>
    );
  }

  // ─── Card variant (default): inner header + body, inline styles ───
  return (
    <div style={{ background: 'rgba(0,0,0,0.25)', borderRadius: 12, border: '1px solid var(--glass-border)', overflow: 'hidden', ...style }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
        <span>{title}</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 }}>
          {subtitle || (count != null ? `${count}개 추출` : '')}
        </span>
      </div>
      <div style={{ padding: '12px 16px' }}>{children}</div>
    </div>
  );
};

export default GlassPanel;
