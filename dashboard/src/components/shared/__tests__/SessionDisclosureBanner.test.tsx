/**
 * SessionDisclosureBanner Tests (Phase 29)
 * =========================================
 * 전역 배너 — warning/exhausted에서만 표시, 닫기·등급 악화 재표시, 설정 링크,
 * API 실패 시 조용히 숨김. 폴링은 disclosureStore 소유이므로 여기선 렌더만 검증.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SessionDisclosureBanner from '../SessionDisclosureBanner';
import { useDisclosureStore } from '../../../stores/disclosureStore';
import { fetchSessionDisclosure, type SessionDisclosure } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  fetchSessionDisclosure: vi.fn(),
}));

const fetchSessionDisclosureMock = vi.mocked(fetchSessionDisclosure);

const WARNING: SessionDisclosure = {
  level: 'warning',
  reset_date: '2026-09-04',
  notices: [],
  limits: [
    {
      kind: 'budget',
      label: '일일 예산',
      limit: 50,
      used: 44,
      remaining: 6,
      usage_percent: 88,
      level: 'warning',
      message: '일일 예산의 80% 이상을 사용했습니다.',
    },
  ],
  markdown: '',
};

const EXHAUSTED: SessionDisclosure = {
  ...WARNING,
  level: 'exhausted',
  limits: [
    {
      kind: 'budget',
      label: '일일 예산',
      limit: 50,
      used: 50,
      remaining: 0,
      usage_percent: 100,
      level: 'exhausted',
      message: '일일 예산이 소진되었습니다 — 리셋까지 대기하거나 예산을 조정하세요.',
    },
  ],
};

const HEALTHY: SessionDisclosure = { ...WARNING, level: 'healthy', limits: [] };

function seedStore(disclosure: SessionDisclosure | null, error = false): void {
  useDisclosureStore.setState({ disclosure, error, loading: false });
}

function resetStore(): void {
  const s = useDisclosureStore.getState();
  if (s._timerId !== null) window.clearInterval(s._timerId);
  useDisclosureStore.setState({ disclosure: null, loading: true, error: false, _refCount: 0, _timerId: null });
}

describe('SessionDisclosureBanner', () => {
  beforeEach(() => {
    fetchSessionDisclosureMock.mockReset();
    resetStore();
  });

  afterEach(() => {
    resetStore();
    vi.restoreAllMocks();
  });

  it('renders nothing for healthy level', () => {
    seedStore(HEALTHY);
    const { container } = render(<SessionDisclosureBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when there is no data yet', () => {
    const { container } = render(<SessionDisclosureBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows warning banner with the worst-limit message and alert role', () => {
    seedStore(WARNING);
    render(<SessionDisclosureBanner />);

    const banner = screen.getByTestId('session-disclosure-banner');
    expect(banner).toHaveClass('level-warning');
    expect(banner).toHaveAttribute('role', 'alert');
    expect(screen.getByText(/세션 한도 주의/)).toBeInTheDocument();
    expect(screen.getByText(/80% 이상을 사용했습니다/)).toBeInTheDocument();
  });

  it('shows exhausted banner with block guidance', () => {
    seedStore(EXHAUSTED);
    render(<SessionDisclosureBanner />);

    expect(screen.getByTestId('session-disclosure-banner')).toHaveClass('level-exhausted');
    expect(screen.getByText(/소진되었습니다/)).toBeInTheDocument();
  });

  it('dispatches agk:pushstate to /settings from the settings link', () => {
    seedStore(WARNING);
    render(<SessionDisclosureBanner />);

    const spy = vi.spyOn(window, 'dispatchEvent');
    fireEvent.click(screen.getByRole('button', { name: '설정에서 확인' }));
    const event = spy.mock.calls.map(([e]) => e).find((e) => e instanceof CustomEvent) as CustomEvent | undefined;
    expect(event?.type).toBe('agk:pushstate');
    expect(event?.detail).toBe('/settings');
    spy.mockRestore();
  });

  it('hides quietly when the last fetch failed (non-critical UX)', () => {
    seedStore(null, true);
    const { container } = render(<SessionDisclosureBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('dismiss stays hidden at the same level, resurfaces on escalation', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(WARNING);
    render(<SessionDisclosureBanner />);
    await waitFor(() => {
      expect(screen.getByTestId('session-disclosure-banner')).toHaveClass('level-warning');
    });

    fireEvent.click(screen.getByRole('button', { name: '세션 고지 배너 닫기' }));
    expect(screen.queryByTestId('session-disclosure-banner')).toBeNull();

    // 동일 등급 재폴링 — 여전히 숨김
    await useDisclosureStore.getState().refresh();
    expect(screen.queryByTestId('session-disclosure-banner')).toBeNull();

    // 등급 악화 — 자동 재표시
    fetchSessionDisclosureMock.mockResolvedValue(EXHAUSTED);
    await useDisclosureStore.getState().refresh();
    await waitFor(() => {
      expect(screen.getByTestId('session-disclosure-banner')).toHaveClass('level-exhausted');
    });
  });

  it('healthy visit resets dismissal, so a later warning resurfaces', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(WARNING);
    render(<SessionDisclosureBanner />);
    await waitFor(() => {
      expect(screen.getByTestId('session-disclosure-banner')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: '세션 고지 배너 닫기' }));
    expect(screen.queryByTestId('session-disclosure-banner')).toBeNull();

    // 완화(healthy) 경유 — 닫기 상태 리셋
    fetchSessionDisclosureMock.mockResolvedValue(HEALTHY);
    await useDisclosureStore.getState().refresh();
    expect(screen.queryByTestId('session-disclosure-banner')).toBeNull(); // healthy는 원래 숨김

    // 재진입(warning) — 새로 표시
    fetchSessionDisclosureMock.mockResolvedValue({ ...WARNING, limits: [{ ...WARNING.limits[0], used: 41, usage_percent: 82 }] });
    await useDisclosureStore.getState().refresh();
    await waitFor(() => {
      expect(screen.getByTestId('session-disclosure-banner')).toBeInTheDocument();
    });
  });
});
