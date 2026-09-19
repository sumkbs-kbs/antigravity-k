/**
 * SessionDisclosurePanel Tests (Phase 9 복원)
 * ============================================
 * 등급별 렌더링, 사용량 포맷, 게이지, 에러·빈 한도 상태를 검증한다.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SessionDisclosurePanel, { formatCountdown } from '../SessionDisclosurePanel';
import { useDisclosureStore } from '../../../stores/disclosureStore';
import { fetchSessionDisclosure, type SessionDisclosure } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  fetchSessionDisclosure: vi.fn(),
}));

const fetchSessionDisclosureMock = vi.mocked(fetchSessionDisclosure);

const HEALTHY: SessionDisclosure = {
  level: 'healthy',
  reset_date: '2026-09-04',
  notices: ['사용 내역은 이 PC에만 저장되며 외부로 전송되지 않습니다.'],
  limits: [
    {
      kind: 'budget',
      label: '일일 예산',
      limit: 50,
      used: 12.5,
      remaining: 37.5,
      usage_percent: 25,
      level: 'healthy',
      message: '일일 예산 여유가 충분합니다.',
    },
    {
      kind: 'action',
      label: '시간당 액션',
      limit: 100,
      used: 30,
      remaining: 70,
      usage_percent: 30,
      level: 'healthy',
      message: '액션 한도 여유가 충분합니다.',
    },
  ],
  markdown: '',
};

const EXHAUSTED: SessionDisclosure = {
  ...HEALTHY,
  level: 'exhausted',
  limits: [
    { ...HEALTHY.limits[0], used: 50, remaining: 0, usage_percent: 100, level: 'exhausted' },
  ],
};

describe('SessionDisclosurePanel', () => {
  beforeEach(() => {
    fetchSessionDisclosureMock.mockReset();
    const s = useDisclosureStore.getState();
    if (s._timerId !== null) window.clearInterval(s._timerId);
    useDisclosureStore.setState({ disclosure: null, loading: true, error: false, _refCount: 0, _timerId: null });
  });

  afterEach(() => {
    const s = useDisclosureStore.getState();
    if (s._timerId !== null) window.clearInterval(s._timerId);
    useDisclosureStore.setState({ _refCount: 0, _timerId: null });
    vi.restoreAllMocks();
  });

  it('renders healthy layout with formatted usage and action counts', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(HEALTHY);
    render(<SessionDisclosurePanel />);

    await waitFor(() => {
      expect(screen.getByTestId('session-disclosure-panel')).toBeInTheDocument();
    });

    expect(screen.getByText(/세션 한도 — 여유/)).toBeInTheDocument();
    expect(screen.getByText('$12.50 / $50.00')).toBeInTheDocument();
    expect(screen.getByText('30 / 100 회')).toBeInTheDocument();
    expect(screen.getByText(/외부로 전송되지 않습니다/)).toBeInTheDocument();
    expect(screen.getByText(/리셋 기준일\(UTC\): 2026-09-04/)).toBeInTheDocument();
    // 예산 카드(25%) 게이지 — 두 한도 카드가 모두 게이지를 렌더링하므로 getAll로 검증
    const gauges = screen.getAllByRole('progressbar');
    expect(gauges).toHaveLength(2);
    expect(gauges[0]).toHaveAttribute('aria-valuenow', '25');
    expect(gauges[1]).toHaveAttribute('aria-valuenow', '30');
  });

  it('renders exhausted styling with a full gauge', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(EXHAUSTED);
    render(<SessionDisclosurePanel />);

    await waitFor(() => {
      expect(screen.getByTestId('session-disclosure-panel')).toHaveClass('level-exhausted');
    });
    expect(screen.getByText(/세션 한도 — 소진/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
  });

  it('includes the reset date from the backend', async () => {
    fetchSessionDisclosureMock.mockResolvedValue(HEALTHY);
    render(<SessionDisclosurePanel />);
    await waitFor(() => expect(screen.getByTestId('session-disclosure-panel')).toBeInTheDocument());
    expect(screen.getByText(/2026-09-04/)).toBeInTheDocument();
  });

  it('renders an error state when the API call fails', async () => {
    fetchSessionDisclosureMock.mockRejectedValue(new Error('network down'));
    render(<SessionDisclosurePanel />);

    await waitFor(() => {
      expect(screen.getByTestId('disclosure-error')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('session-disclosure-panel')).toBeNull();
  });

  it('renders the no-limits empty state', async () => {
    fetchSessionDisclosureMock.mockResolvedValue({ ...HEALTHY, limits: [] });
    render(<SessionDisclosurePanel />);

    await waitFor(() => {
      expect(screen.getByText(/활성화된 한도가 없습니다/)).toBeInTheDocument();
    });
  });

  it('renders a time-until-reset countdown in the exhausted-state message when reset_at is provided', async () => {
    const futureIso = new Date(Date.now() + 3600 * 2000 + 45 * 1000).toISOString();
    const EXHAUSTED_WITH_RESET: SessionDisclosure = {
      ...EXHAUSTED,
      limits: [
        {
          ...EXHAUSTED.limits[0],
          reset_at: futureIso,
          seconds_until_reset: 7245,
        },
      ],
    };
    fetchSessionDisclosureMock.mockResolvedValue(EXHAUSTED_WITH_RESET);
    render(<SessionDisclosurePanel />);

    await waitFor(() => {
      expect(screen.getByTestId('reset-countdown')).toBeInTheDocument();
    });

    expect(screen.getByText(/소진되었습니다 — 리셋까지/)).toBeInTheDocument();
    const countdownEl = screen.getByTestId('reset-countdown');
    expect(countdownEl.textContent).toMatch(/\d+시간\s+\d+분\s+\d+초/);
  });

  it('formatCountdown utility formats hours, minutes, and seconds properly', () => {
    expect(formatCountdown(3665)).toBe('1시간 01분 05초');
    expect(formatCountdown(125)).toBe('2분 05초');
    expect(formatCountdown(45)).toBe('45초');
    expect(formatCountdown(0)).toBe('0초');
  });
});
