/**
 * SystemTelemetricsBar — TERMINAL-7 Header Telemetry Bar
 * ======================================================
 * Row 1: ■ SSAK-AI / RESEARCH GROUP | [chat] [studio] [models] [git] [skills] | SYS · HH:MM:SSZ
 * Row 2: BUILD | UPTIME | NODE | CPU | MEM | VAULT | LINK
 *
 * CR-10
 * -----
 * 모든 값은 실제 API 관측에서 온다. 값이 없으면 0/false/true로 뭉개지 않고 `UNKNOWN`을
 * 표시하며, 마지막 **성공** 관측 시각(`observedAt`)으로 live / stale / offline을 구분한다.
 * BUILD는 실행 중인 서버 버전(+빌드 식별자)이고, 번들 버전이 다르면 함께 표시해 오해를 막는다.
 * UPTIME은 **API 서버 프로세스**의 가동 시간이다(호스트 uptime·탭 열린 시간과 무관).
 */

import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useUiStore, type SystemConnectionState } from '../../stores/uiStore';
import { getUiBuildInfo } from '../../utils/uiBuildInfo';

/** 폴링 주기(10s)의 3배 — 이보다 오래 관측이 없으면 stale로 본다. */
export const STALE_AFTER_MS = 30_000;

const UNKNOWN = 'UNKNOWN';

const CONNECTION_LABEL: Record<SystemConnectionState, string> = {
  unknown: 'UNKNOWN',
  live: 'LIVE',
  stale: 'STALE',
  disconnected: 'OFFLINE',
};

export function formatUptime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  if (days > 0) return `${days}D ${pad(hours)}H ${pad(minutes)}M`;
  if (hours > 0) return `${hours}H ${pad(minutes)}M`;
  return `${minutes}M ${pad(secs)}S`;
}

export function formatAge(observedAt: number, now: number): string {
  const elapsed = Math.max(0, now - observedAt);
  if (elapsed < 1000) return 'now';
  const seconds = Math.floor(elapsed / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

/** 마지막 관측 시각과 현재 시각으로 연결 상태를 파생한다. */
export function deriveConnectionState(
  base: SystemConnectionState,
  observedAt: number | null,
  now: number,
): SystemConnectionState {
  if (base === 'disconnected') return 'disconnected';
  if (observedAt === null || base === 'unknown') return 'unknown';
  return now - observedAt > STALE_AFTER_MS ? 'stale' : 'live';
}

export const SystemTelemetricsBar: React.FC = () => {
  const { systemStatus } = useUiStore();
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const utc = new Date(now);
  const timeString = `${String(utc.getUTCHours()).padStart(2, '0')}:${String(
    utc.getUTCMinutes(),
  ).padStart(2, '0')}:${String(utc.getUTCSeconds()).padStart(2, '0')}Z`;

  const { observedAt, state: baseState, healthy, version, buildId, processId } = systemStatus;

  const connection = deriveConnectionState(baseState, observedAt, now);
  const isLive = connection === 'live';

  // BUILD: 실제 서버 버전(+빌드 식별자). 번들 버전과 다르면 둘 다 보여준다.
  const ui = getUiBuildInfo();
  const serverBuild = version ? `v${version}${buildId ? ` · ${buildId}` : ''}` : null;
  const buildLabel =
    serverBuild === null
      ? UNKNOWN
      : ui.version === version
        ? serverBuild
        : `${serverBuild} (ui v${ui.version})`;

  // UPTIME: 서버가 준 값 + 마지막 관측 이후 경과분. 0은 재시작 직후의 유효값이다.
  const uptimeLabel =
    systemStatus.uptimeSeconds === null
      ? UNKNOWN
      : formatUptime(
          systemStatus.uptimeSeconds +
            (isLive && observedAt !== null ? (now - observedAt) / 1000 : 0),
        );

  const healthState = healthy === null ? UNKNOWN : healthy ? 'NOMINAL' : 'DEGRADED';
  const nodeLabel =
    processId === null ? UNKNOWN : `PID-${processId} · ${healthState}`;

  const cpuLabel =
    systemStatus.cpuPercent === null ? UNKNOWN : `${systemStatus.cpuPercent.toFixed(1)}%`;
  const memLabel =
    systemStatus.memoryPercent === null
      ? UNKNOWN
      : `${systemStatus.memoryPercent.toFixed(1)}%`;
  const vaultLabel =
    systemStatus.ragFiles === null ? UNKNOWN : `${systemStatus.ragFiles} INDEXED`;

  const linkValueClass =
    connection === 'live'
      ? 'telemetrics-stat-green'
      : connection === 'unknown'
        ? 'telemetrics-stat-dim'
        : 'telemetrics-stat-amber';
  const linkDetail =
    observedAt === null ? '' : ` · ${formatAge(observedAt, now)}`;

  const indicatorColor =
    healthy === true
      ? 'var(--terminal-green)'
      : healthy === false
        ? 'var(--error-color)'
        : 'var(--text-muted)';

  return (
    <header className="telemetrics-bar" aria-label="System Telemetrics Bar">
      {/* ── Row 1: Brand, Fast Links, System Time ────────────────── */}
      <div className="telemetrics-top-row">
        <div className="telemetrics-brand">
          <span
            className="telemetrics-indicator"
            style={{ background: indicatorColor, boxShadow: `0 0 6px ${indicatorColor}` }}
          />
          <span>SSAK-AI / RESEARCH GROUP</span>
        </div>

        <nav className="telemetrics-links" aria-label="빠른 바로가기">
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              `telemetrics-link ${isActive ? 'active' : ''}`
            }
          >
            [chat]
          </NavLink>
          <NavLink
            to="/studio"
            className={({ isActive }) =>
              `telemetrics-link ${isActive ? 'active' : ''}`
            }
          >
            [studio]
          </NavLink>
          <NavLink
            to="/models"
            className={({ isActive }) =>
              `telemetrics-link ${isActive ? 'active' : ''}`
            }
          >
            [models]
          </NavLink>
          <NavLink
            to="/git"
            className={({ isActive }) =>
              `telemetrics-link ${isActive ? 'active' : ''}`
            }
          >
            [git]
          </NavLink>
          <NavLink
            to="/skills"
            className={({ isActive }) =>
              `telemetrics-link ${isActive ? 'active' : ''}`
            }
          >
            [skills]
          </NavLink>
          <NavLink
            to="/history"
            className={({ isActive }) =>
              `telemetrics-link ${isActive ? 'active' : ''}`
            }
          >
            [history]
          </NavLink>
        </nav>

        <div className="telemetrics-clock">
          <span>SYS · {timeString}</span>
        </div>
      </div>

      {/* ── Row 2: Telemetrics Telemetry Stats ───────────────────── */}
      {/* UI-01 (axe scrollable-region-focusable): 가로 스크롤 영역을 키보드 접근 가능하게 */}
      <div className="telemetrics-sub-row" tabIndex={0} aria-label="시스템 텔레메트리 상세 지표">
        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">BUILD:</span>
          <span className="telemetrics-stat-val" data-testid="telemetrics-build">
            {buildLabel}
          </span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">UPTIME:</span>
          <span className="telemetrics-stat-val" data-testid="telemetrics-uptime">
            {uptimeLabel}
          </span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">NODE:</span>
          <span
            className={
              healthy === true ? 'telemetrics-stat-green' : 'telemetrics-stat-dim'
            }
            data-testid="telemetrics-node"
            data-health={healthy === null ? 'unknown' : String(healthy)}
          >
            {nodeLabel}
          </span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">CPU:</span>
          <span className="telemetrics-stat-val" data-testid="telemetrics-cpu">
            {cpuLabel}
          </span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">MEM:</span>
          <span className="telemetrics-stat-val" data-testid="telemetrics-mem">
            {memLabel}
          </span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">VAULT:</span>
          <span className="telemetrics-stat-amber" data-testid="telemetrics-vault">
            {vaultLabel}
          </span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">LINK:</span>
          <span
            className={linkValueClass}
            data-testid="telemetrics-link"
            data-connection={connection}
          >
            {CONNECTION_LABEL[connection]}
            {linkDetail}
          </span>
        </div>
      </div>
    </header>
  );
};

export default SystemTelemetricsBar;
