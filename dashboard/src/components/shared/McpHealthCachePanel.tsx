/**
 * McpHealthCachePanel — MCP 서버 헬스 캐시 대시보드
 * ==================================================
 * 서버별 initialize / list_tools 결과와 실패 원인을 표시합니다.
 * (mcp_upgrade_report P2 / BENCHMARK_UPGRADE_PLAN §6)
 *
 * GET  /api/mcp/health
 * POST /api/mcp/health/refresh  — 프로브 후 캐시 갱신
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  fetchMcpHealth,
  refreshMcpHealth,
  type McpHealthEntry,
  type McpHealthResponse,
} from '../../api/client';
import GlassPanel from './GlassPanel';

interface Props {
  refreshInterval?: number;
}

const STATUS_META: Record<string, { color: string; icon: string; label: string }> = {
  healthy: { color: '#10b981', icon: '🟢', label: '정상' },
  error: { color: '#ef4444', icon: '🔴', label: '오류' },
  blocked: { color: '#f59e0b', icon: '⛔', label: '차단' },
  configured: { color: '#8b8fa3', icon: '⚪', label: '구성됨' },
  unknown: { color: '#6b7280', icon: '❔', label: '미확인' },
};

function formatCheckedAt(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return '—';
  try {
    return new Date(ts * 1000).toLocaleString('ko-KR', { hour12: false });
  } catch {
    return '—';
  }
}

const McpHealthCachePanel: React.FC<Props> = ({ refreshInterval = 20000 }) => {
  const [data, setData] = useState<McpHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await fetchMcpHealth();
      setData(next);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Connection error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    const interval = setInterval(() => void load(), refreshInterval);
    return () => {
      clearTimeout(t);
      clearInterval(interval);
    };
  }, [load, refreshInterval]);

  const handleProbe = async () => {
    setProbing(true);
    try {
      const next = await refreshMcpHealth();
      setData(next);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Probe failed');
    } finally {
      setProbing(false);
    }
  };

  const servers: McpHealthEntry[] = data?.servers ?? [];
  const summary = data?.summary;

  return (
    <GlassPanel title="🔌 MCP 서버 헬스 캐시" variant="section" className="settings-section">
      {error && (
        <div style={{ fontSize: 12, color: '#ef4444', marginBottom: 12 }} role="alert">
          ⚠️ {error}
        </div>
      )}

      {loading && !data ? (
        <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>
          MCP 헬스 로딩 중...
        </div>
      ) : (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
              gap: 12,
              marginBottom: 16,
            }}
          >
            {(
              [
                ['total', '전체', '#7c6aef'],
                ['healthy', '정상', '#10b981'],
                ['error', '오류', '#ef4444'],
                ['blocked', '차단', '#f59e0b'],
                ['configured', '미프로브', '#8b8fa3'],
              ] as const
            ).map(([key, label, color]) => (
              <div
                key={key}
                style={{
                  background: `${color}14`,
                  border: `1px solid ${color}33`,
                  borderRadius: 8,
                  padding: '10px 12px',
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}
                >
                  {label}
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, color, marginTop: 2 }}>
                  {summary?.[key] ?? 0}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              소스: {data?.source || '—'}
              {data?.probed_at ? ` · 프로브 ${formatCheckedAt(data.probed_at)}` : ''}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="glass-btn small" onClick={() => void load()} style={{ fontSize: 11 }}>
                🔄 새로고침
              </button>
              <button
                className="glass-btn small"
                onClick={() => void handleProbe()}
                disabled={probing}
                style={{ fontSize: 11 }}
                data-testid="mcp-health-probe"
              >
                {probing ? '프로브 중...' : '🩺 헬스 프로브'}
              </button>
            </div>
          </div>

          {servers.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '24px 0',
                color: 'var(--text-muted)',
                fontSize: 13,
              }}
            >
              <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }}>🔌</div>
              <div>구성된 MCP 서버가 없습니다.</div>
              <div style={{ fontSize: 11, marginTop: 4 }}>
                프로젝트 루트에 .mcp.json 을 추가하거나 AGK_MCP_CONFIG 를 설정하세요.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {servers.map((server) => {
                const meta = STATUS_META[server.status] ?? STATUS_META.unknown;
                const isOpen = expanded === server.name;
                return (
                  <div
                    key={server.name}
                    className="mcp-health-row"
                    role="button"
                    tabIndex={0}
                    data-testid={`mcp-health-row-${server.name}`}
                    onClick={() => setExpanded(isOpen ? null : server.name)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setExpanded(isOpen ? null : server.name);
                      }
                    }}
                    style={{
                      cursor: 'pointer',
                      padding: '8px 12px',
                      borderRadius: 8,
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.06)',
                      fontSize: 12,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                        <span aria-hidden>{meta.icon}</span>
                        <strong style={{ color: 'var(--text-primary)' }}>{server.name}</strong>
                        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{server.transport}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 12, color: 'var(--text-muted)', fontSize: 11, flexShrink: 0 }}>
                        <span style={{ color: meta.color, fontWeight: 600 }}>{meta.label}</span>
                        <span>🛠️ {server.tool_count}</span>
                        {server.latency_ms != null && <span>{server.latency_ms.toFixed(0)}ms</span>}
                        <span>{isOpen ? '▲' : '▼'}</span>
                      </div>
                    </div>
                    {isOpen && (
                      <div
                        style={{
                          marginTop: 8,
                          paddingTop: 8,
                          borderTop: '1px solid rgba(255,255,255,0.06)',
                          display: 'grid',
                          gridTemplateColumns: '1fr 1fr',
                          gap: '4px 16px',
                          fontSize: 11,
                          color: 'var(--text-secondary)',
                        }}
                      >
                        <div>
                          명령/URL: <strong style={{ wordBreak: 'break-all' }}>{server.command || '—'}</strong>
                        </div>
                        <div>
                          검사 시각: <strong>{formatCheckedAt(server.checked_at)}</strong>
                        </div>
                        <div>
                          초기화: <strong>{server.initialized ? '성공' : '미완료'}</strong>
                        </div>
                        <div>
                          소스: <strong>{server.source || '—'}</strong>
                        </div>
                        {server.error && (
                          <div style={{ gridColumn: '1 / -1', color: '#ef4444' }}>
                            실패 원인: <strong>{server.error}</strong>
                          </div>
                        )}
                        {server.tools.length > 0 && (
                          <div style={{ gridColumn: '1 / -1' }}>
                            도구:{' '}
                            {server.tools.slice(0, 12).map((t) => (
                              <span key={t} className="tool-chip" style={{ marginRight: 4 }}>
                                {t}
                              </span>
                            ))}
                            {server.tools.length > 12 && (
                              <span style={{ color: 'var(--text-muted)' }}>+{server.tools.length - 12}</span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </GlassPanel>
  );
};

export default McpHealthCachePanel;
