/**
 * McpOAuthPanel — MCP OAuth 2.1 interactive authorization
 * ========================================================
 * Start / complete (via browser callback) / revoke OAuth for remote MCP servers.
 * (mcp_upgrade_report P1 / BENCHMARK_UPGRADE_PLAN §6)
 *
 * GET  /api/mcp/oauth/status
 * POST /api/mcp/oauth/start
 * POST /api/mcp/oauth/revoke
 * GET  /api/mcp/oauth/callback  (browser redirect)
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  fetchMcpOAuthStatus,
  startMcpOAuth,
  revokeMcpOAuth,
  type McpOAuthServerStatus,
  type McpOAuthStatusResponse,
} from '../../api/client';
import GlassPanel from './GlassPanel';

interface Props {
  refreshInterval?: number;
}

const McpOAuthPanel: React.FC<Props> = ({ refreshInterval = 15000 }) => {
  const [data, setData] = useState<McpOAuthStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await fetchMcpOAuthStatus();
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
    const onMsg = (ev: MessageEvent) => {
      const payload = ev.data as { type?: string; ok?: boolean; server?: string } | null;
      if (payload && payload.type === 'mcp-oauth') {
        setInfo(
          payload.ok
            ? `OAuth 연결 완료: ${payload.server || ''}`
            : 'OAuth 콜백이 실패했습니다. 다시 시도하세요.',
        );
        void load();
      }
    };
    window.addEventListener('message', onMsg);
    return () => {
      clearTimeout(t);
      clearInterval(interval);
      window.removeEventListener('message', onMsg);
    };
  }, [load, refreshInterval]);

  const handleConnect = async (server: McpOAuthServerStatus) => {
    setBusy(server.name);
    setInfo(null);
    try {
      const started = await startMcpOAuth(server.name);
      if (!started.ok || !started.authorization_url) {
        setError('authorization_url 을 받지 못했습니다.');
        return;
      }
      setInfo(`브라우저에서 승인하세요: ${server.name}`);
      window.open(started.authorization_url, 'ssak-mcp-oauth', 'noopener,noreferrer,width=560,height=720');
      // Poll a bit faster after starting
      void load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'OAuth start failed');
    } finally {
      setBusy(null);
    }
  };

  const handleRevoke = async (server: McpOAuthServerStatus) => {
    setBusy(server.name);
    setInfo(null);
    try {
      await revokeMcpOAuth(server.name);
      setInfo(`연결 해제됨: ${server.name}`);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Revoke failed');
    } finally {
      setBusy(null);
    }
  };

  const servers = (data?.servers ?? []).filter((s) => s.supports_oauth);
  const summary = data?.summary;

  return (
    <GlassPanel title="🔐 MCP OAuth 2.1" variant="section" className="settings-section">
      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 0, marginBottom: 12, lineHeight: 1.5 }}>
        원격 HTTP MCP 서버에 Authorization Code + PKCE 로 연결합니다.
        토큰은 암호화 vault에 저장되며 대시보드에 노출되지 않습니다.
      </p>

      {error && (
        <div style={{ fontSize: 12, color: '#ef4444', marginBottom: 12 }} role="alert">
          ⚠️ {error}
        </div>
      )}
      {info && (
        <div style={{ fontSize: 12, color: '#10b981', marginBottom: 12 }} role="status">
          ✅ {info}
        </div>
      )}

      {loading && !data ? (
        <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>
          OAuth 상태 로딩 중...
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
                ['oauth_capable', 'OAuth 대상', '#3b82f6'],
                ['connected', '연결됨', '#10b981'],
              ] as const
            ).map(([key, label, color]) => (
              <div
                key={key}
                style={{
                  background: `${color}14`,
                  border: `1px solid ${color}33`,
                  borderRadius: 10,
                  padding: '10px 12px',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color }} data-testid={`mcp-oauth-summary-${key}`}>
                  {summary?.[key] ?? 0}
                </div>
              </div>
            ))}
          </div>

          {servers.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              OAuth가 필요한 원격 HTTP MCP 서버가 없습니다. `.mcp.json` 에 `url` 기반 서버를 추가하세요.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {servers.map((server) => {
                const connected = Boolean(server.connected);
                return (
                  <div
                    key={server.name}
                    data-testid={`mcp-oauth-row-${server.name}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 12px',
                      borderRadius: 10,
                      border: '1px solid var(--glass-border)',
                      background: 'rgba(255,255,255,0.02)',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{server.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                        {server.transport} · {server.url || '—'}
                      </div>
                      <div style={{ fontSize: 11, marginTop: 4, color: connected ? '#10b981' : '#8b8fa3' }}>
                        {connected ? '🟢 연결됨' : '⚪ 미연결'}
                        {server.status?.expired ? ' · 만료됨(재연결 필요)' : ''}
                      </div>
                    </div>
                    {connected ? (
                      <button
                        type="button"
                        className="btn-ghost"
                        disabled={busy === server.name}
                        onClick={() => void handleRevoke(server)}
                        data-testid={`mcp-oauth-revoke-${server.name}`}
                      >
                        {busy === server.name ? '…' : '연결 해제'}
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={busy === server.name}
                        onClick={() => void handleConnect(server)}
                        data-testid={`mcp-oauth-connect-${server.name}`}
                      >
                        {busy === server.name ? '…' : 'OAuth 연결'}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 14, lineHeight: 1.45 }}>
            수동 확인: Settings → OAuth 연결 → 브라우저 승인 → 콜백 후 상태가 「연결됨」으로 바뀌는지 확인.
            E2E 브라우저 콜백이 불가한 환경에서는 API 테스트(`tests/test_mcp_oauth.py`)로 코드 경로를 검증합니다.
          </div>
        </>
      )}
    </GlassPanel>
  );
};

export default McpOAuthPanel;
