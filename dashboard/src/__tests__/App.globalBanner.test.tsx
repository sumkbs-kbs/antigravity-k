/**
 * App 레벨 전역 배너 마운트 테스트 (Phase 51)
 * ============================================
 * Phase 13 사양 복원 확인: SessionDisclosureBanner가 AppContent 최상단(모든 라우트 공통)에
 * 마운트돼 있어 settings를 열지 않고도 warning/exhausted가 모든 페이지에서 보인다.
 *
 * 컴포넌트 단위 동작(닫기/재표시/링크)은 SessionDisclosureBanner.test.tsx가 담당하고,
 * 여기선 "앱 셸에 실제로 붙어 있는가" — 전역 가시성 계약 — 만 검증한다.
 */

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { useDisclosureStore } from '../stores/disclosureStore';
import { useUiStore } from '../stores/uiStore';
import { fetchSessionDisclosure, type SessionDisclosure } from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    fetchSessionDisclosure: vi.fn(),
  };
});

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

function resetStores(): void {
  const s = useDisclosureStore.getState();
  if (s._timerId !== null) window.clearInterval(s._timerId);
  useDisclosureStore.setState({
    disclosure: null,
    loading: true,
    error: false,
    _refCount: 0,
    _timerId: null,
    _notifiedExhausted: false,
  });
}

describe('App global disclosure banner (Phase 13 사양 복원)', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    sessionStorage.setItem('ag_access_token', 'valid-token');
    useUiStore.setState({ pinModalVisible: false });
    fetchSessionDisclosureMock.mockReset();
    fetchSessionDisclosureMock.mockResolvedValue(WARNING);
    resetStores();
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 })),
    );
    vi.stubGlobal(
      'WebSocket',
      class {
        static readonly CONNECTING = 0;
        static readonly OPEN = 1;
        readyState = 1;
        onopen = null;
        onmessage = null;
        onclose = null;
        onerror = null;
        close() {}
      },
    );
  });

  afterEach(() => {
    cleanup();
    resetStores();
    vi.unstubAllGlobals();
    window.history.pushState({}, '', '/');
  });

  it('shows the warning banner on the chat page without opening settings', async () => {
    render(<App />);
    expect(await screen.findByTestId('session-disclosure-banner')).toHaveClass('level-warning');
  });

  it('shows the banner on every routed page', async () => {
    for (const path of ['/', '/models', '/settings', '/git']) {
      window.history.pushState({}, '', path);
      const { unmount } = render(<App />);
      const banner = await screen.findByTestId('session-disclosure-banner');
      expect(banner).toHaveClass('level-warning');
      unmount();
    }
  });

  it('keeps the banner mounted above route content (outside <main>)', async () => {
    render(<App />);
    const banner = await screen.findByTestId('session-disclosure-banner');
    // 배너는 app-right-panel 직속 — 라우트 <main> 바깥이라 어떤 페이지가 떠도 항상 위에 있다.
    expect(banner.parentElement).not.toBe(null);
    expect(banner.parentElement?.querySelector('main')).not.toBe(null);
    expect(banner.parentElement!.tagName.toLowerCase()).toBe('div');
  });

  it('still renders nothing for a healthy session', async () => {
    fetchSessionDisclosureMock.mockResolvedValue({ ...WARNING, level: 'healthy', limits: [] });
    const { container } = render(<App />);
    await waitFor(() => expect(fetchSessionDisclosureMock).toHaveBeenCalled());
    expect(container.querySelector('[data-testid="session-disclosure-banner"]')).toBeNull();
  });
});
