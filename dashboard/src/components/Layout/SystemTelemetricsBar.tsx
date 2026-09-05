/**
 * SystemTelemetricsBar — TERMINAL-7 Exact Header Telemetry Bar
 * ============================================================
 * Row 1: ■ SSAK-AI / RESEARCH GROUP | [chat] [studio] [models] [git] [skills] | SYS · HH:MM:SSZ
 * Row 2: BUILD: 0.8.0-RC | UPTIME: ... | NODE: LOCAL-01 · NOMINAL | CPU/MEM | CTRL: READY
 */

import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';

export const SystemTelemetricsBar: React.FC = () => {
  const { systemStatus } = useUiStore();
  const [timeString, setTimeString] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const hours = String(now.getUTCHours()).padStart(2, '0');
      const minutes = String(now.getUTCMinutes()).padStart(2, '0');
      const seconds = String(now.getUTCSeconds()).padStart(2, '0');
      setTimeString(`${hours}:${minutes}:${seconds}Z`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const cpuPercent = systemStatus.cpuPercent ?? 0;
  const memoryMb = systemStatus.memoryMb ?? 0;
  const ragFiles = systemStatus.ragFiles ?? 0;
  const isHealthy = systemStatus.healthy ?? true;

  return (
    <header className="telemetrics-bar" aria-label="System Telemetrics Bar">
      {/* ── Row 1: Brand, Fast Links, System Time ────────────────── */}
      <div className="telemetrics-top-row">
        <div className="telemetrics-brand">
          <span
            className="telemetrics-indicator"
            style={{
              background: isHealthy ? 'var(--terminal-green)' : 'var(--error-color)',
              boxShadow: isHealthy
                ? '0 0 6px var(--terminal-green)'
                : '0 0 6px var(--error-color)',
            }}
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
          <span>SYS · {timeString || '12:00:00Z'}</span>
        </div>
      </div>

      {/* ── Row 2: Telemetrics Telemetry Stats ───────────────────── */}
      <div className="telemetrics-sub-row">
        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">BUILD:</span>
          <span className="telemetrics-stat-val">v0.8.0-RC</span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">UPTIME:</span>
          <span className="telemetrics-stat-val">14D 08H 12M</span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">NODE:</span>
          <span className={isHealthy ? 'telemetrics-stat-green' : 'telemetrics-stat-amber'}>
            LOCAL-01 · {isHealthy ? 'NOMINAL' : 'DEGRADED'}
          </span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">CPU:</span>
          <span className="telemetrics-stat-val">{cpuPercent.toFixed(1)}%</span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">MEM:</span>
          <span className="telemetrics-stat-val">{memoryMb.toFixed(0)} MB</span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">VAULT:</span>
          <span className="telemetrics-stat-amber">{ragFiles} INDEXED</span>
        </div>

        <div className="telemetrics-stat-item">
          <span className="telemetrics-stat-label">CTRL:</span>
          <span className="telemetrics-stat-green">OPEN INTAKE WAVE 01</span>
        </div>
      </div>
    </header>
  );
};

export default SystemTelemetricsBar;
