// @ts-nocheck
import React from 'react';
import { MCPServer, esc } from './types';
import EmptyState from './EmptyState';

interface MCPTabProps {
  servers: MCPServer[];
}

const MCPTab: React.FC<MCPTabProps> = ({ servers }) => {
  if (servers.length === 0) {
    return (
      <EmptyState
        icon="🔌"
        title="MCP 서버가 없습니다."
        subtitle="스킬에 MCP 설정이 추가되면 여기에 표시됩니다."
      />
    );
  }

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <span className="status-badge active" style={{ fontSize: 12 }}>
          {servers.length} servers
        </span>
      </div>
      <div className="skills-grid">
        {servers.map(server => {
          const status = server.status || 'unknown';
          const statusColor = status === 'running' || status === 'active'
            ? '#34d399'
            : status === 'error'
              ? '#ef4444'
              : '#8b8fa3';
          const statusIcon = status === 'running' || status === 'active'
            ? '🟢'
            : status === 'error'
              ? '🔴'
              : '⚪';
          const tools = (server.tools || server.available_tools || []) as any[];
          const toolCount = tools.length;

          return (
            <div key={server.name || server.server_name} className="glass-panel skill-card">
              <div className="skill-card-header">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 14 }}>🔌</span>
                    <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                      {esc(server.name || server.server_name || 'Unknown')}
                    </strong>
                  </div>
                  {server.description && (
                    <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                      {server.description}
                    </p>
                  )}
                </div>
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: 11,
                  color: statusColor,
                  fontWeight: 500,
                }}>
                  {statusIcon} {status}
                </span>
              </div>
              <div className="skill-card-meta" style={{
                display: 'flex',
                gap: 12,
                fontSize: 11,
                color: 'var(--text-muted)',
                flexWrap: 'wrap',
                alignItems: 'center',
              }}>
                {server.skill_name && <span>🏪 {esc(server.skill_name)}</span>}
                <span>🛠️ {toolCount} tools</span>
                {server.transport && <span>🔗 {esc(server.transport)}</span>}
              </div>
              {toolCount > 0 && (
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--glass-border)' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {tools.slice(0, 8).map((t: any, i: number) => (
                      <span key={i} className="tool-chip">
                        {esc(typeof t === 'string' ? t : (t.name || t.function?.name || 'tool'))}
                      </span>
                    ))}
                    {toolCount > 8 && (
                      <span className="tool-chip" style={{ color: 'var(--text-muted)' }}>
                        +{toolCount - 8} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
};

export default MCPTab;
