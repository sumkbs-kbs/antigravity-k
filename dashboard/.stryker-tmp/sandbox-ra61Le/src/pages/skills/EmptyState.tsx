// @ts-nocheck
import React from 'react';

interface EmptyStateProps {
  icon: string;
  title: string;
  subtitle: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, subtitle }) => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '60px 20px',
    textAlign: 'center',
  }}>
    <span style={{ fontSize: 48, marginBottom: 16, opacity: 0.4 }}>{icon}</span>
    <h3 style={{ margin: '0 0 8px', fontSize: 16, color: 'var(--text-secondary)', fontWeight: 500 }}>{title}</h3>
    <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)', maxWidth: 400 }}>{subtitle}</p>
  </div>
);

export default EmptyState;
