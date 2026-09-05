/**
 * MetricItem + MetricDivider — Metrics bar display
 * ==================================================
 * Used in MetricsBar to display key metrics with icon, value, and label.
 */

import React from 'react';

interface MetricItemProps {
  icon: string;
  value: string;
  label: string;
  color?: string;
}

const MetricItem: React.FC<MetricItemProps> = ({ icon, value, label, color }) => (
  <div className="metric-item">
    <span className="metric-item-icon" aria-hidden="true">{icon}</span>
    <div className="metric-item-copy">
      <div style={{ fontSize: 13, fontWeight: 600, color: color || 'var(--text-primary)' }}>{value}</div>
      <div className="metric-item-label">{label}</div>
    </div>
  </div>
);

const MetricDivider: React.FC = () => (
  <div style={{ width: 1, height: 32, background: 'var(--glass-border)', flexShrink: 0 }} />
);

export { MetricItem, MetricDivider };
export type { MetricItemProps };
