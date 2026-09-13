/**
 * CR-06 — 설정 상태가 서버의 진실을 반영하는지 고정한다.
 * =====================================================
 * 발견 F02: 초기 GET이 실패해도 화면은 "기본값 폼"(예산 50/한도 100/searxng)을
 * 정상 설정처럼 보여주고 저장까지 허용했다. 이 파일은 그 결함과 함께,
 *
 *  - loading/load-error에서 저장 금지 + 오류/재시도 UI(C06-01/C06-02),
 *  - 서버 관리 값이 브라우저의 오래된 값보다 우선(C06-04),
 *  - 유효한 0 예산/0 한도가 기본값으로 대체되지 않음(C06-04),
 *  - 연속 클릭이 중복 요청을 만들지 않음(C06-03),
 *  - 저장 실패 시 비밀 아닌 입력 유지 + 401은 기존 PIN 흐름 안내(C06-03)
 *
 * 를 고정한다. 이 스펙은 구현 전에 실행하면 T1~T4가 실패해야 한다(재현 증거).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const apiMocks = vi.hoisted(() => ({
  fetchSettings: vi.fn(),
  saveSettings: vi.fn(),
  deleteSettingsKeys: vi.fn(),
  fetchLogLevels: vi.fn(),
  setLogLevel: vi.fn(),
  setAllLogLevels: vi.fn(),
  setDebugMode: vi.fn(),
  isAuthRequiredError: vi.fn(() => false),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/shared/CacheStatsPanel', () => ({ default: () => <div /> }));
vi.mock('../components/shared/McpHealthCachePanel', () => ({ default: () => <div /> }));
vi.mock('../components/shared/McpOAuthPanel', () => ({ default: () => <div /> }));
vi.mock('../components/shared/ModelOperationsPanel', () => ({ default: () => <div /> }));

import SettingsPage from './SettingsPage';

const STORAGE_KEY = 'agk_user_settings:v1';

function storedSettings(): Record<string, unknown> {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
}

function testId(id: string): HTMLElement {
  return screen.getByTestId(id);
}

async function renderPage(): Promise<void> {
  render(<SettingsPage />);
}

function saveButton(): HTMLElement | null {
  return screen.queryByTestId('settings-save');
}

describe('SettingsPage · CR-06', () => {
  beforeEach(() => {
    localStorage.clear();
    apiMocks.fetchLogLevels.mockResolvedValue({ ok: true, loggers: [], debug_mode: false, count: 0 });
    apiMocks.saveSettings.mockResolvedValue({ ok: true, updated: 1, message: 'saved' });
    apiMocks.deleteSettingsKeys.mockResolvedValue({ ok: true, deleted: 0 });
    apiMocks.isAuthRequiredError.mockReturnValue(false);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ── C06-01 / C06-02 ────────────────────────────────────────────
  it('does not show a saveable default form when the initial load fails', async () => {
    apiMocks.fetchSettings.mockRejectedValue(new Error('HTTP 503: Unavailable'));

    await renderPage();

    await waitFor(() => expect(testId('settings-load-error')).toBeInTheDocument());
    expect(screen.getByTestId('settings-retry')).toBeInTheDocument();
    // 서버의 진실을 모르는 상태에서 기본값을 저장할 수 있으면 안 된다.
    const save = saveButton();
    if (save) expect(save).toBeDisabled();
    expect(screen.queryByDisplayValue('50')).not.toBeInTheDocument();
  });

  it('recovers to the server truth after a retry succeeds', async () => {
    apiMocks.fetchSettings
      .mockRejectedValueOnce(new Error('HTTP 500: Internal Server Error'))
      .mockResolvedValueOnce({ model: { name: 'server-model', provider: 'openrouter' } });

    await renderPage();
    await waitFor(() => expect(testId('settings-load-error')).toBeInTheDocument());

    fireEvent.click(testId('settings-retry'));

    await waitFor(() => expect(screen.getByDisplayValue('server-model')).toBeInTheDocument());
    expect(screen.queryByTestId('settings-load-error')).not.toBeInTheDocument();
    expect(saveButton()).not.toBeDisabled();
  });

  // ── C06-04: 서버 값 우선 + 0값 보존 ────────────────────────────
  it('prefers the server value over a stale browser preference', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ default_model: 'stale-browser-model' }));
    apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'server-model' } });

    await renderPage();

    await waitFor(() => expect(screen.getByDisplayValue('server-model')).toBeInTheDocument());
    expect(screen.queryByDisplayValue('stale-browser-model')).not.toBeInTheDocument();
  });

  it('keeps a valid zero budget instead of replacing it with a default', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ daily_budget_usd: '50', hourly_action_limit: '100' }),
    );
    apiMocks.fetchSettings.mockResolvedValue({
      model: { name: 'server-model' },
      cost: { daily_budget_usd: 0, hourly_action_limit: 0 },
    });

    await renderPage();

    await waitFor(() => expect(testId('settings-daily-budget')).toBeInTheDocument());
    expect((testId('settings-daily-budget') as HTMLInputElement).value).toBe('0');
    expect((testId('settings-hourly-limit') as HTMLInputElement).value).toBe('0');

    fireEvent.click(testId('settings-save'));
    await waitFor(() => expect(storedSettings()['daily_budget_usd']).toBe('0'));
    expect(storedSettings()['hourly_action_limit']).toBe('0');
  });

  it('falls back to the stored browser preference only when the server omits the value', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ default_model: 'browser-only-model' }));
    apiMocks.fetchSettings.mockResolvedValue({ server: { host: '127.0.0.1' } });

    await renderPage();

    await waitFor(() => expect(screen.getByDisplayValue('browser-only-model')).toBeInTheDocument());
  });

  it('shows the server-enforced cost values as read-only context', async () => {
    apiMocks.fetchSettings.mockResolvedValue({
      model: { name: 'server-model' },
      cost: { daily_budget_usd: 12.5, hourly_action_limit: 7 },
    });

    await renderPage();

    await waitFor(() => expect(testId('settings-server-cost')).toBeInTheDocument());
    expect(testId('settings-server-cost').textContent).toContain('12.5');
    expect(testId('settings-server-cost').textContent).toContain('7');
  });

  // ── C06-03: 중복 클릭 / 실패 복구 / 401 ────────────────────────
  it('sends one request while a save is in flight', async () => {
    let resolveSave: ((value: { ok: boolean; updated: number }) => void) | undefined;
    apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'server-model' } });
    apiMocks.saveSettings.mockImplementation(
      () =>
        new Promise(resolve => {
          resolveSave = resolve as typeof resolveSave;
        }),
    );

    await renderPage();
    await waitFor(() => expect(testId('settings-save')).toBeInTheDocument());
    fireEvent.change(testId('api-key-input-OPENAI_API_KEY'), { target: { value: 'sk-cr06-fake' } });

    const save = testId('settings-save');
    fireEvent.click(save);
    fireEvent.click(save);
    fireEvent.click(save);

    expect(apiMocks.saveSettings).toHaveBeenCalledTimes(1);
    expect(testId('settings-save')).toBeDisabled();
    expect(testId('settings-save').textContent).toContain('저장 중');

    resolveSave?.({ ok: true, updated: 1 });
    await waitFor(() => expect(testId('settings-save')).not.toBeDisabled());
  });

  it('keeps non-secret inputs and re-enables save after a failed save', async () => {
    apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'server-model' } });
    apiMocks.saveSettings.mockRejectedValue(new Error('HTTP 500: Internal Server Error'));

    await renderPage();
    await waitFor(() => expect(testId('settings-save')).toBeInTheDocument());

    fireEvent.change(testId('settings-default-model'), { target: { value: 'edited-model' } });
    fireEvent.change(testId('api-key-input-OPENAI_API_KEY'), { target: { value: 'sk-cr06-keep' } });
    fireEvent.click(testId('settings-save'));

    await waitFor(() => expect(testId('settings-save-error')).toBeInTheDocument());
    expect((testId('settings-default-model') as HTMLInputElement).value).toBe('edited-model');
    expect((testId('api-key-input-OPENAI_API_KEY') as HTMLInputElement).value).toBe('sk-cr06-keep');
    expect(testId('settings-save')).not.toBeDisabled();
    expect(screen.queryByText(/저장 완료/)).not.toBeInTheDocument();
  });

  it('routes an auth failure to the existing PIN flow message', async () => {
    apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'server-model' } });
    apiMocks.saveSettings.mockRejectedValue(new Error('HTTP 401: Unauthorized'));
    apiMocks.isAuthRequiredError.mockReturnValue(true);

    await renderPage();
    await waitFor(() => expect(testId('settings-save')).toBeInTheDocument());

    fireEvent.change(testId('api-key-input-OPENAI_API_KEY'), { target: { value: 'sk-cr06-auth' } });
    fireEvent.click(testId('settings-save'));

    await waitFor(() => expect(testId('settings-save-error')).toBeInTheDocument());
    expect(testId('settings-save-error').textContent).toMatch(/PIN|인증/);
    expect(screen.queryByText(/저장 완료/)).not.toBeInTheDocument();
  });

  it('refreshes server-managed values from the server after a successful save', async () => {
    apiMocks.fetchSettings
      .mockResolvedValueOnce({ model: { name: 'model-before' } })
      .mockResolvedValueOnce({
        model: { name: 'model-after' },
        cost: { daily_budget_usd: 3, hourly_action_limit: 4 },
      });
    apiMocks.saveSettings.mockResolvedValue({ ok: true, updated: 1, message: 'saved' });

    await renderPage();
    await waitFor(() => expect(screen.getByDisplayValue('model-before')).toBeInTheDocument());

    fireEvent.change(testId('api-key-input-OPENAI_API_KEY'), { target: { value: 'sk-cr06-refresh' } });
    fireEvent.click(testId('settings-save'));

    await waitFor(() => expect(screen.getByDisplayValue('model-after')).toBeInTheDocument());
    expect(screen.getByText(/저장 완료|저장했습니다/)).toBeInTheDocument();
  });
});
