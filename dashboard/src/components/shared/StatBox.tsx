/**
 * StatBox — Label + value pair display
 * ======================================
 * Used for metrics like "종가 ₩943,000", "등락률 +1.51%".
 */

import React from 'react';

interface Props {
  label: string;
  value: string;
  bold?: boolean;
  color?: string;
}

const StatBox: React.FC<Props> = ({ label, value, bold, color }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
    <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{label}</span>
    <span style={{ fontWeight: bold ? 600 : 400, fontSize: bold ? 14 : 13, color: color || 'var(--text-primary)' }}>
      {value}
    </span>
  </div>
);

export default StatBox;
