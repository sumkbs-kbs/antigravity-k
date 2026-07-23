/**
 * CacheStatsPanel — API Response Cache Statistics Widget
 * =======================================================
 * Displays ApiCache metrics: total entries, hit ratio, tag count,
 * memory estimate, and recent cache entries with TTL/age/hits.
 *
 * Fetches data from GET /api/system/cache-stats every 15 seconds.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { fetchCacheStats, type CacheStats } from '../../api/client';
import GlassPanel from './GlassPanel';

interface Props {
  /** Refresh interval in ms (default: 15000) */
  refreshInterval?: number;
}

const CacheStatsPanel: React.FC<Props> = ({ refreshInterval = 15000 }) => {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchCacheStats();
      if (data.ok && 'stats' in data) {
        setStats(data.stats);
        setError(null);
      } else if ('error' in data) {
        setError(data.error || 'Failed to load cache stats');
      }
    } catch (err: any) {
      setError(err.message || 'Connection error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, refreshInterval);
    return () => clearInterval(interval);
  }, [loadStats, refreshInterval]);

  const hitRatio = stats ? (stats.hit_ratio * 100).toFixed(1) : '0.0';
  const hitRatioColor = stats && stats.hit_ratio > 0.8 ? '#10b981' : stats && stats.hit_ratio > 0.5 ? '#f59e0b' : '#6b7280';

  return (
    <GlassPanel title="📦 API 응답 캐시 통계" variant="section" className="settings-section">
      {error && (
        <div style={{ fontSize: 12, color: '#ef4444', marginBottom: 12 }}>
          ⚠️ {error}
        </div>
      )}

      {loading && !stats ? (
        <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>
          <span className="dex-spinner-mini" style={{
            display: 'inline-block', width: 12, height: 12,
            border: '2px solid var(--glass-border)', borderTopColor: 'var(--accent-color)',
            borderRadius: '50%', animation: 'dex-spin 0.8s linear infinite',
            marginRight: 8, verticalAlign: 'middle',
          }} />
          캐시 통계 로딩 중...
        </div>
      ) : stats ? (
        <>
          {/* ─── Metric Cards Row ──────────────────────────────── */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: 12, marginBottom: 16,
          }}>
            {/* Entries */}
            <div style={{
              background: 'rgba(124,106,239,0.08)',
              border: '1px solid rgba(124,106,239,0.2)',
              borderRadius: 8, padding: '12px 14px',
            }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                캐시 엔트리
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent-color)', marginTop: 4 }}>
                {stats.total_entries}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                {stats.total_tags}개 태그 그룹
              </div>
            </div>

            {/* Hit Ratio */}
            <div style={{
              background: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: 8, padding: '12px 14px',
            }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                히트율
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: hitRatioColor, marginTop: 4 }}>
                {hitRatio}%
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                {stats.hits} hit / {stats.misses} miss
              </div>
            </div>

            {/* Memory */}
            <div style={{
              background: 'rgba(6,182,212,0.08)',
              border: '1px solid rgba(6,182,212,0.2)',
              borderRadius: 8, padding: '12px 14px',
            }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                추정 메모리
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#06b6d4', marginTop: 4 }}>
                {stats.memory_estimate_kb < 1 ? '<1' : stats.memory_estimate_kb.toFixed(1)}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                KB (응답 데이터)
              </div>
            </div>

            {/* Requests */}
            <div style={{
              background: 'rgba(251,191,36,0.08)',
              border: '1px solid rgba(251,191,36,0.2)',
              borderRadius: 8, padding: '12px 14px',
            }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                총 요청
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#f59e0b', marginTop: 4 }}>
                {(stats.hits + stats.misses).toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                {stats.hits > 0 || stats.misses > 0 ? '캐시 사용 중' : '아직 요청 없음'}
              </div>
            </div>
          </div>

          {/* ─── Hit Ratio Progress Bar ────────────────────────── */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
              <span>히트율</span>
              <span>{hitRatio}%</span>
            </div>
            <div style={{
              height: 6, background: 'rgba(255,255,255,0.06)',
              borderRadius: 3, overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', width: `${Math.min(100, stats.hit_ratio * 100)}%`,
                background: `linear-gradient(90deg, ${hitRatioColor}, ${stats.hit_ratio > 0.8 ? '#34d399' : '#fbbf24'})`,
                borderRadius: 3, transition: 'width 0.5s ease',
              }} />
            </div>
          </div>

          {/* ─── Refresh Button ────────────────────────────────── */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            <button
              className="glass-btn small"
              onClick={loadStats}
              style={{ fontSize: 11 }}
            >
              🔄 새로고침
            </button>
          </div>

          {/* ─── Entries List ──────────────────────────────────── */}
          {stats.entries.length > 0 && (
            <>
              <div style={{
                fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)',
                marginBottom: 8, display: 'flex', justifyContent: 'space-between',
              }}>
                <span>최근 캐시 엔트리</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  총 {stats.entries.length}개 (최근순)
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {stats.entries.slice(0, 15).map((entry) => (
                  <div
                    key={entry.key}
                    className="cache-entry-row"
                    onClick={() => setExpandedEntry(expandedEntry === entry.key ? null : entry.key)}
                    style={{
                      cursor: 'pointer',
                      padding: '6px 10px',
                      borderRadius: 6,
                      background: entry.remaining_ttl <= 0 ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.06)',
                      transition: 'background 0.15s',
                      fontSize: 12,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                        <span style={{
                          width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                          background: entry.remaining_ttl > entry.ttl * 0.5 ? '#10b981'
                            : entry.remaining_ttl > 0 ? '#f59e0b'
                            : '#ef4444',
                        }} />
                        <span style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap', color: 'var(--text-primary)',
                        }}>
                          {entry.key.length > 50 ? entry.key.slice(0, 50) + '...' : entry.key}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 12, flexShrink: 0, color: 'var(--text-muted)', fontSize: 11 }}>
                        <span title="TTL / 남은 TTL">{entry.remaining_ttl.toFixed(0)}s</span>
                        <span title="조회 횟수">👁️ {entry.hits}</span>
                        <span style={{ fontSize: 10 }}>{expandedEntry === entry.key ? '▲' : '▼'}</span>
                      </div>
                    </div>
                    {expandedEntry === entry.key && (
                      <div style={{
                        marginTop: 6, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.06)',
                        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px',
                        fontSize: 11, color: 'var(--text-secondary)',
                      }}>
                        <div>TTL: <strong>{entry.ttl}s</strong></div>
                        <div>Age: <strong>{entry.age}s</strong></div>
                        <div>남은 TTL: <strong>{entry.remaining_ttl.toFixed(1)}s</strong></div>
                        <div>조회: <strong>{entry.hits}회</strong></div>
                        <div style={{ gridColumn: '1 / -1' }}>
                          태그: <strong>{entry.tags.length > 0 ? entry.tags.join(', ') : '(없음)'}</strong>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {stats.entries.length > 15 && (
                <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                  ... 외 {stats.entries.length - 15}개 엔트리
                </div>
              )}
            </>
          )}

          {/* ─── Empty State ───────────────────────────────────── */}
          {stats.entries.length === 0 && (
            <div style={{
              textAlign: 'center', padding: '24px 0',
              color: 'var(--text-muted)', fontSize: 13,
            }}>
              <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }}>📭</div>
              <div>아직 캐시된 API 응답이 없습니다.</div>
              <div style={{ fontSize: 11, marginTop: 4 }}>
                API 요청이 발생하면 자동으로 캐싱됩니다.
              </div>
            </div>
          )}
        </>
      ) : null}
    </GlassPanel>
  );
};

export default CacheStatsPanel;
