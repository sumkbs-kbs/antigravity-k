/**
 * SessionDisclosureBanner — 전역 세션 고지 배너 (Phase 29 복원, 스토어 통합)
 * ===========================================================================
 * Phase 13 사양 + Phase 29 스토어 통합:
 *  - healthy/null → 렌더링 없음. warning(호박 ⚠️)/exhausted(적색 ⛔)만 표시
 *  - role="alert" + aria-live="polite"
 *  - 닫기: 동일 등급에서는 세션 동안 숨김, 등급 악화(warning→exhausted) 시 자동 재표시
 *  - "설정에서 확인" — agk:pushstate 커스텀 이벤트로 SPA 라우팅
 *  - API 실패 시 조용히 숨김 (비필수 UX — 오류 토스트 없음)
 *  - 폴링 없음: disclosureStore 공유 인터벌 소비 (구독만으로 데이터 수신)
 */

import React, { useEffect, useRef, useState } from 'react';
import { useDisclosureStore } from '../../stores/disclosureStore';

const LEVEL_LABEL: Record<string, string> = {
  warning: '주의',
  exhausted: '소진',
};

const SessionDisclosureBanner: React.FC = () => {
  const disclosure = useDisclosureStore((s) => s.disclosure);
  const subscribe = useDisclosureStore((s) => s.subscribe);
  const unsubscribe = useDisclosureStore((s) => s.unsubscribe);

  const [dismissedLevel, setDismissedLevel] = useState<string | null>(null);
  const prevLevelRef = useRef<string | null>(null);

  useEffect(() => {
    subscribe();
    return unsubscribe;
  }, [subscribe, unsubscribe]);

  const level = disclosure?.level ?? null;
  const active = level === 'warning' || level === 'exhausted';

  // 등급 악화 감지 — dismissed 등급에서 악화되면 닫기 해제
  useEffect(() => {
    const prev = prevLevelRef.current;
    prevLevelRef.current = level;
    if (level && prev && level !== prev && dismissedLevel && dismissedLevel !== level) {
      setDismissedLevel(null);
    }
  }, [level, dismissedLevel]);

  if (!active || !disclosure || dismissedLevel === level) {
    return null;
  }

  const isExhausted = level === 'exhausted';
  const icon = isExhausted ? '⛔' : '⚠️';
  const worst = disclosure.limits.reduce<{ label: string; message: string } | null>((acc, l) => {
    if (l.level !== level) return acc;
    return acc ?? { label: l.label, message: l.message };
  }, null);

  return (
    <div
      className={`session-disclosure-banner ${isExhausted ? 'level-exhausted' : 'level-warning'}`}
      role="alert"
      aria-live="polite"
      data-testid="session-disclosure-banner"
    >
      <span className="banner-icon" aria-hidden>
        {icon}
      </span>
      <span className="banner-text">
        <strong>세션 한도 {LEVEL_LABEL[level ?? '']}:</strong>{' '}
        {worst ? worst.message : '한도 사용량이 임계선을 넘었습니다.'}
      </span>
      <button
        type="button"
        className="banner-link"
        onClick={() => window.dispatchEvent(new CustomEvent('agk:pushstate', { detail: '/settings' }))}
      >
        설정에서 확인
      </button>
      <button
        type="button"
        className="banner-dismiss"
        title="이 등급에서는 숨기기 (악화 시 다시 표시)"
        aria-label="세션 고지 배너 닫기"
        onClick={() => setDismissedLevel(level)}
      >
        ✕
      </button>
    </div>
  );
};

export default SessionDisclosureBanner;
