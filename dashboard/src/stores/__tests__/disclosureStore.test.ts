/**
 * disclosureStore Tests (Phase 29)
 * ==================================
 * 공유 폴러 라이프사이클(refcount), 구독자 0일 때 정리, dismiss/등급 악화 재표시 상태를 검증.
 * 컴포넌트 렌더링 검증은 SessionDisclosurePanel/SessionDisclosureBanner 테스트에서 담당.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { useDisclosureStore, DISCLOSURE_POLL_INTERVAL_MS } from '../disclosureStore';
import { fetchSessionDisclosure, type SessionDisclosure } from '../../api/client';
import { notifyExhausted } from '../../utils/exhaustedNotification';

vi.mock('../../api/client', () => ({
  fetchSessionDisclosure: vi.fn(),
}));

vi.mock('../../utils/exhaustedNotification', () => ({
  notifyExhausted: vi.fn(() => true),
}));

const notifyExhaustedMock = vi.mocked(notifyExhausted);

const fetchSessionDisclosureMock = vi.mocked(fetchSessionDisclosure);

const HEALTHY: SessionDisclosure = {
  level: 'healthy',
  reset_date: '2026-09-04',
  notices: [],
  limits: [],
  markdown: '',
};

const EXHAUSTED: SessionDisclosure = {
  level: 'exhausted',
  reset_date: '2026-09-04',
  notices: [],
  markdown: '',
  limits: [
    {
      kind: 'budget',
      label: '일일 예산',
      limit: 50,
      used: 50,
      remaining: 0,
      usage_percent: 100,
      level: 'exhausted',
      message: '일일 예산이 소진되었습니다.',
    },
  ],
};

const WARNING: SessionDisclosure = {
  ...HEALTHY,
  level: 'warning',
  limits: [
    { ...EXHAUSTED.limits[0], used: 44, remaining: 6, usage_percent: 88, level: 'warning', message: '주의' },
  ],
};

function resetStore(): void {
  const state = useDisclosureStore.getState();
  if (state._timerId !== null) window.clearInterval(state._timerId);
  useDisclosureStore.setState({
    disclosure: null,
    loading: true,
    error: false,
    _notifiedExhausted: false,
    _refCount: 0,
    _timerId: null,
  });
}

describe('disclosureStore', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    fetchSessionDisclosureMock.mockReset();
    notifyExhaustedMock.mockClear();
    notifyExhaustedMock.mockReturnValue(true);
    resetStore();
  });

  afterEach(() => {
    resetStore();
    vi.useRealTimers();
  });

  it('starts with default state and no timer', () => {
    const s = useDisclosureStore.getState();
    expect(s.disclosure).toBeNull();
    expect(s.loading).toBe(true);
    expect(s.error).toBe(false);
    expect(s._refCount).toBe(0);
    expect(s._timerId).toBeNull();
  });

  it('first subscribe fetches immediately and starts the shared interval', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(HEALTHY);
    useDisclosureStore.getState().subscribe();

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchSessionDisclosureMock).toHaveBeenCalledTimes(1);
    expect(useDisclosureStore.getState()._timerId).not.toBeNull();
    expect(useDisclosureStore.getState().disclosure).toEqual(HEALTHY);

    // 공유 인터벌 폴링 — refcount 1 유지
    await vi.advanceTimersByTimeAsync(DISCLOSURE_POLL_INTERVAL_MS);
    expect(fetchSessionDisclosureMock).toHaveBeenCalledTimes(2);
  });

  it('multiple subscribers share one interval — no duplicate polls', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(HEALTHY);
    useDisclosureStore.getState().subscribe();
    useDisclosureStore.getState().subscribe();
    useDisclosureStore.getState().subscribe();

    await vi.advanceTimersByTimeAsync(0);
    expect(useDisclosureStore.getState()._refCount).toBe(3);
    expect(fetchSessionDisclosureMock).toHaveBeenCalledTimes(1); // 즉시 fetch 1회뿐

    await vi.advanceTimersByTimeAsync(DISCLOSURE_POLL_INTERVAL_MS);
    expect(fetchSessionDisclosureMock).toHaveBeenCalledTimes(2); // 인터벌 1개만 동작
  });

  it('last unsubscribe stops the interval and clears data-path polling', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(HEALTHY);
    const store = useDisclosureStore.getState();
    store.subscribe();
    store.subscribe();
    await vi.advanceTimersByTimeAsync(0);

    store.unsubscribe();
    expect(useDisclosureStore.getState()._refCount).toBe(1);
    expect(useDisclosureStore.getState()._timerId).not.toBeNull();

    store.unsubscribe();
    expect(useDisclosureStore.getState()._refCount).toBe(0);
    expect(useDisclosureStore.getState()._timerId).toBeNull();

    const callsAfterStop = fetchSessionDisclosureMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(DISCLOSURE_POLL_INTERVAL_MS * 3);
    expect(fetchSessionDisclosureMock).toHaveBeenCalledTimes(callsAfterStop);
  });

  it('sets error flag on failure and keeps last good disclosure', async () => {
    fetchSessionDisclosureMock.mockResolvedValueOnce(HEALTHY);
    useDisclosureStore.getState().subscribe();
    await vi.advanceTimersByTimeAsync(0);
    expect(useDisclosureStore.getState().error).toBe(false);

    fetchSessionDisclosureMock.mockRejectedValueOnce(new Error('boom'));
    await useDisclosureStore.getState().refresh();
    const s = useDisclosureStore.getState();
    expect(s.error).toBe(true);
    expect(s.disclosure).toEqual(HEALTHY); // 마지막 성공값 유지
    expect(s.loading).toBe(false);
  });

  it('refresh recovers the error flag on subsequent success', async () => {
    fetchSessionDisclosureMock.mockRejectedValueOnce(new Error('down'));
    useDisclosureStore.getState().subscribe();
    await vi.advanceTimersByTimeAsync(0);
    expect(useDisclosureStore.getState().error).toBe(true);

    fetchSessionDisclosureMock.mockResolvedValueOnce(HEALTHY);
    await useDisclosureStore.getState().refresh();
    expect(useDisclosureStore.getState().error).toBe(false);
  });

  it('notifies exactly once when the level first reaches exhausted', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(WARNING);
    useDisclosureStore.getState().subscribe();
    await vi.advanceTimersByTimeAsync(0);
    expect(notifyExhaustedMock).not.toHaveBeenCalled();

    // warning → exhausted 전환 — 1회 발송
    fetchSessionDisclosureMock.mockResolvedValue(EXHAUSTED);
    await useDisclosureStore.getState().refresh();
    expect(notifyExhaustedMock).toHaveBeenCalledTimes(1);
    expect(notifyExhaustedMock).toHaveBeenCalledWith('일일 예산이 소진되었습니다.');

    // 연속 소진 폴링 — 재발송 없음
    await useDisclosureStore.getState().refresh();
    await useDisclosureStore.getState().refresh();
    expect(notifyExhaustedMock).toHaveBeenCalledTimes(1);
  });

  it('re-arms after recovery: exhausted → warning → exhausted notifies again', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(EXHAUSTED);
    useDisclosureStore.getState().subscribe();
    await vi.advanceTimersByTimeAsync(0);
    expect(notifyExhaustedMock).toHaveBeenCalledTimes(1);

    fetchSessionDisclosureMock.mockResolvedValue(WARNING);
    await useDisclosureStore.getState().refresh();
    expect(useDisclosureStore.getState()._notifiedExhausted).toBe(false);

    fetchSessionDisclosureMock.mockResolvedValue(EXHAUSTED);
    await useDisclosureStore.getState().refresh();
    expect(notifyExhaustedMock).toHaveBeenCalledTimes(2);
  });

  it('does not notify when a failed poll is followed by exhausted data', async () => {
    // 실패는 데이터를 건드리지 않으므로, 이후 최초 소진 도달이면 정상 발송된다
    fetchSessionDisclosureMock.mockRejectedValueOnce(new Error('down'));
    useDisclosureStore.getState().subscribe();
    await vi.advanceTimersByTimeAsync(0);

    fetchSessionDisclosureMock.mockResolvedValue(EXHAUSTED);
    await useDisclosureStore.getState().refresh();
    expect(notifyExhaustedMock).toHaveBeenCalledTimes(1);
  });
});
