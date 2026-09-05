/**
 * SessionDisclosurePanel — 세션 한도 고지 카드
 * ==============================================
 * 벤치마킹 출처: freebuff "session limits + data-use notice before you start" UX.
 * 등급(healthy/warning/exhausted)에 따라 색상이 바뀌는 배너 + 한도별 카드(게이지·등급 배지).
 * 데이터·폴링은 disclosureStore 공유 스토어 소유 (Phase 29 — 배너와 하나의 인터벌).
 * 등급 산정 단일 진실원은 backend session_disclosure.py.
 */

import React, { useEffect, useState } from 'react';
import type { LimitDisclosure, SessionDisclosure } from '../../api/client';
import { useDisclosureStore } from '../../stores/disclosureStore';

const LEVEL_META: Record<
  SessionDisclosure['level'],
  { icon: string; label: string; className: string }
> = {
  healthy: { icon: '✅', label: '여유', className: 'level-healthy' },
  warning: { icon: '⚠️', label: '주의', className: 'level-warning' },
  exhausted: { icon: '⛔', label: '소진', className: 'level-exhausted' },
};

export function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  const pad = (n: number) => String(n).padStart(2, '0');

  if (hours > 0) {
    return `${hours}시간 ${pad(minutes)}분 ${pad(secs)}초`;
  }
  if (minutes > 0) {
    return `${minutes}분 ${pad(secs)}초`;
  }
  return `${secs}초`;
}

export function renderLimitMessage(
  limit: LimitDisclosure,
  now: number,
  fallbackResetDate?: string
): React.ReactNode {
  if (limit.level !== 'exhausted') {
    return limit.message;
  }

  let remainingSec: number | null = null;
  if (limit.reset_at) {
    const target = new Date(limit.reset_at).getTime();
    if (!isNaN(target)) {
      remainingSec = Math.max(0, Math.floor((target - now) / 1000));
    }
  } else if (limit.seconds_until_reset != null && limit.seconds_until_reset > 0) {
    remainingSec = limit.seconds_until_reset;
  } else if (limit.kind === 'budget' && fallbackResetDate) {
    const nextMidnight = new Date(`${fallbackResetDate}T00:00:00Z`).getTime() + 86_400_000;
    if (!isNaN(nextMidnight) && nextMidnight > now) {
      remainingSec = Math.max(0, Math.floor((nextMidnight - now) / 1000));
    }
  }

  if (remainingSec != null) {
    const countdownText = formatCountdown(remainingSec);
    const prefix = limit.kind === 'budget'
      ? '일일 예산이 소진되었습니다 — 리셋까지 '
      : '시간당 액션 한도에 도달했습니다 — 리셋까지 ';
    const suffix = limit.kind === 'budget'
      ? ' 남음 (대기하거나 예산을 조정하세요).'
      : ' 남음 (잠시 후 재시도하세요).';

    return (
      <>
        {prefix}
        <span className="limit-countdown font-mono font-semibold" data-testid="reset-countdown">
          {countdownText}
        </span>
        {suffix}
      </>
    );
  }

  // fallback regex match if message already has countdown text
  const match = limit.message.match(/^(.*리셋까지\s+)(.+?)(\s+남음.*)$/);
  if (match) {
    return (
      <>
        {match[1]}
        <span className="limit-countdown font-mono font-semibold" data-testid="reset-countdown">
          {match[2]}
        </span>
        {match[3]}
      </>
    );
  }

  return limit.message;
}

function formatUsed(limit: LimitDisclosure): string {
  if (limit.kind === 'budget') {
    return `$${limit.used.toFixed(2)} / $${limit.limit.toFixed(2)}`;
  }
  return `${Math.round(limit.used)} / ${Math.round(limit.limit)} 회`;
}

const SessionDisclosurePanel: React.FC = () => {
  const disclosure = useDisclosureStore((s) => s.disclosure);
  const error = useDisclosureStore((s) => s.error);
  const loading = useDisclosureStore((s) => s.loading);
  const refresh = useDisclosureStore((s) => s.refresh);
  const subscribe = useDisclosureStore((s) => s.subscribe);
  const unsubscribe = useDisclosureStore((s) => s.unsubscribe);

  const [now, setNow] = useState(() => Date.now());

  const hasExhausted = disclosure?.limits.some((l) => l.level === 'exhausted') ?? false;

  useEffect(() => {
    if (!hasExhausted) return;
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [hasExhausted]);

  useEffect(() => {
    subscribe();
    return unsubscribe;
  }, [subscribe, unsubscribe]);

  if (loading) {
    return (
      <div className="session-disclosure-panel" data-testid="disclosure-loading">
        <span className="disclosure-loading-spinner" aria-label="고지 로딩 중" />
      </div>
    );
  }

  if (error || !disclosure) {
    return (
      <div className="session-disclosure-panel" data-testid="disclosure-error">
        <span className="disclosure-error-text">세션 고지를 불러올 수 없습니다.</span>
      </div>
    );
  }

  const meta = LEVEL_META[disclosure.level] ?? LEVEL_META.healthy;

  return (
    <div className={`session-disclosure-panel ${meta.className}`} data-testid="session-disclosure-panel">
      <div className="disclosure-banner">
        <span className="disclosure-icon" aria-hidden>
          {meta.icon}
        </span>
        <span className="disclosure-title">세션 한도 — {meta.label}</span>
        <button
          type="button"
          className="disclosure-refresh"
          title="세션 고지 새로고침"
          onClick={() => void refresh()}
        >
          ↻
        </button>
      </div>

      {disclosure.limits.length === 0 ? (
        <p className="disclosure-empty">활성화된 한도가 없습니다. 자유롭게 사용하세요.</p>
      ) : (
        <div className="disclosure-limits">
          {disclosure.limits.map((limit) => {
            const limitMeta = LEVEL_META[limit.level] ?? LEVEL_META.healthy;
            return (
              <div key={limit.kind} className={`disclosure-limit-card ${limitMeta.className}`}>
                <div className="limit-card-header">
                  <span className="limit-label">{limit.label}</span>
                  <span className="limit-usage">{formatUsed(limit)}</span>
                  <span className={`limit-level-badge ${limitMeta.className}`}>{limitMeta.icon} {limitMeta.label}</span>
                </div>
                <div
                  className="limit-gauge"
                  role="progressbar"
                  aria-valuenow={Math.min(100, Math.round(limit.usage_percent))}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="limit-gauge-fill"
                    style={{ width: `${Math.min(100, limit.usage_percent)}%` }}
                  />
                </div>
                <p className="limit-message">{renderLimitMessage(limit, now, disclosure.reset_date)}</p>
              </div>
            );
          })}
        </div>
      )}

      {disclosure.notices.length > 0 && (
        <ul className="disclosure-notices">
          {disclosure.notices.map((notice) => (
            <li key={notice}>{notice}</li>
          ))}
        </ul>
      )}

      <p className="disclosure-reset-date">리셋 기준일(UTC): {disclosure.reset_date}</p>
    </div>
  );
};

export default SessionDisclosurePanel;
