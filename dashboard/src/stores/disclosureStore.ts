/**
 * disclosureStore — 세션 고지 공유 스토어 (Phase 29/30)
 * ======================================================
 * 배너(전역)와 설정 카드가 **하나의 폴링 인터벌**을 공유한다.
 * - refcount 기반 폴러: 구독자(마운트된 컴포넌트)가 1명 이상일 때만 30초 폴링
 *   → 페이지 어디에도 고지 표면이 없으면 네트워크 요청 0건
 * - fetch는 client.ts의 fetchSessionDisclosure (zod 검증 단일 경로)
 * - 등급 산정 단일 진실원: backend session_disclosure.py (프론트는 렌더만)
 * - Phase 30: 등급이 처음 exhausted에 도달하면 브라우저 알림 1회 발송
 *   (에피소드당 1회 — 완화 후 재소진 시 다시 발송, _notifiedExhaustedRef 플래그)
 */

import { create } from 'zustand';
import { fetchSessionDisclosure, type SessionDisclosure } from '../api/client';
import { notifyExhausted } from '../utils/exhaustedNotification';

export const DISCLOSURE_POLL_INTERVAL_MS = 30_000;

export interface DisclosureState {
  /** 마지막으로 받은 고지 (없으면 null) */
  disclosure: SessionDisclosure | null;
  /** 최초 fetch 완료 전 로딩 */
  loading: boolean;
  /** 마지막 fetch 실패 여부 (재시도는 다음 인터벌 또는 refresh) */
  error: boolean;
  /** 현재 에피소드에서 소진 알림을 이미 보냈는지 (완화 시 리셋) — 내부 관리용 */
  _notifiedExhausted: boolean;
  /** 폴링 구독 수 — 내부 관리용 */
  _refCount: number;
  /** 폴러 핸들 — 내부 관리용 (테스트 접근용으로만 노출) */
  _timerId: number | null;
  /** 공용 fetch — 실패 시 error 플래그만 (데이터는 유지: 마지막 성공값 렌더 유지) */
  refresh: () => Promise<void>;
  /** 컴포넌트 마운트 시 호출 — refcount 증가, 0→1이면 즉시 fetch + 인터벌 시작 */
  subscribe: () => void;
  /** 컴포넌트 언마운트 시 호출 — refcount 감소, 1→0이면 인터벌 정리 */
  unsubscribe: () => void;
}

function maybeNotifyExhausted(previous: SessionDisclosure | null, next: SessionDisclosure): boolean {
  if (next.level !== 'exhausted') return false;
  // 같은 에피소드(연속 소진)면 재발송하지 않는다 — 전환 시점(warning→exhausted, null→exhausted)만
  if (previous?.level === 'exhausted') return false;
  const message =
    next.limits.find((l) => l.level === 'exhausted')?.message ?? '세션 한도에 도달했습니다.';
  return notifyExhausted(message);
}

export const useDisclosureStore = create<DisclosureState>((set, get) => ({
  disclosure: null,
  loading: true,
  error: false,
  _notifiedExhausted: false,
  _refCount: 0,
  _timerId: null,

  refresh: async () => {
    let next: SessionDisclosure;
    try {
      next = await fetchSessionDisclosure();
    } catch {
      set({ error: true, loading: false });
      return;
    }
    // 방어: 클라이언트(zod) 통과 응답만 처리 — 형태가 아니면 실패 폴링으로 간주
    if (!next || typeof next.level !== 'string') {
      set({ error: true, loading: false });
      return;
    }
    const previous = get().disclosure;
    let notified = get()._notifiedExhausted;
    if (!notified && maybeNotifyExhausted(previous, next)) {
      notified = true;
    }
    // 소진에서 완화로 돌아오면 플래그 리셋 — 다음 에피소드에서 다시 알림
    if (previous?.level === 'exhausted' && next.level !== 'exhausted') {
      notified = false;
    }
    set({ disclosure: next, error: false, loading: false, _notifiedExhausted: notified });
  },

  subscribe: () => {
    const nextCount = get()._refCount + 1;
    set({ _refCount: nextCount });
    if (nextCount === 1) {
      void get().refresh();
      set((s) => {
        if (s._timerId !== null) return {};
        const timerId = window.setInterval(
          () => void useDisclosureStore.getState().refresh(),
          DISCLOSURE_POLL_INTERVAL_MS,
        );
        return { _timerId: timerId };
      });
    }
  },

  unsubscribe: () => {
    const nextCount = Math.max(0, get()._refCount - 1);
    set({ _refCount: nextCount });
    if (nextCount === 0 && get()._timerId !== null) {
      window.clearInterval(get()._timerId!);
      set({ _timerId: null });
    }
  },
}));
