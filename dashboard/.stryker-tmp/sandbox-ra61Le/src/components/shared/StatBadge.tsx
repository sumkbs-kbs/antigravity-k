/**
 * StatBadge — Inline statistic badge
 * ====================================
 * Used for summary counts like "📈 주식 3건".
 */
// @ts-nocheck


import React from 'react';

interface Props {
  icon: string;
  text: string;
  color?: string;
}

const StatBadge: React.FC<Props> = ({ icon, text, color }) => (
  <span style={{ padding: '2px 8px', borderRadius: 4, background: color || 'rgba(124,106,239,0.1)', fontSize: 12 }}>
    {icon} {text}
  </span>
);

export default StatBadge;
