/**
 * EmptyData — Empty state placeholder
 * =====================================
 * Shown when a panel has no data to display.
 */

import React from 'react';

interface Props {
  msg: string;
}

const EmptyData: React.FC<Props> = ({ msg }) => (
  <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
    {msg}
  </div>
);

export default EmptyData;
