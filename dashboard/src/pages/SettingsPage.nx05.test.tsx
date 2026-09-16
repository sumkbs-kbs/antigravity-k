/**
 * NX-05 — PIN 변경 = 전체 세션 폐기 (대시보드 계약)
 *
 * 서버는 PIN 변경 시 auth epoch 을 올려 이전 토큰/ticket 을 모두 무효화한다.
 * 화면이 저장 토큰을 그대로 두면 이후 모든 요청이 401 로 반복되므로, PIN 변경
 * 응답의 `reauth_required` 를 받은 즉시 자격증명을 지우고 재로그인(PIN 모달)을
 * 띄워야 한다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const apiMocks = vi.hoisted(() => ({
  fetchSettings: vi.fn(),
  saveSettings: vi.fn(),
  deleteSettingsKeys: vi.fn(),
  changeAccessPin: vi.fn(),
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
import { useUiStore } from '../stores/uiStore';

const TOKEN_KEY = 'ag_access_token';

async function renderLoadedPage(): Promise<void> {
  render(<SettingsPage />);
  await waitFor(() => expect(screen.getByText('시스템 설정')).toBeInTheDocument());
}

async function submitPinChange(): Promise<void> {
  fireEvent.change(screen.getByTestId('settings-current-pin'), { target: { value: '0000' } });
  fireEvent.change(screen.getByTestId('settings-new-pin'), { target: { value: '1234' } });
  fireEvent.change(screen.getByTestId('settings-confirm-pin'), { target: { value: '1234' } });
  fireEvent.click(screen.getByTestId('settings-change-pin'));
}

describe('NX-05 SettingsPage PIN change revocation', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    useUiStore.setState({ pinModalVisible: false });
    apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'model-a', provider: 'openrouter' } });
    apiMocks.fetchLogLevels.mockResolvedValue({ ok: true, loggers: [], debug_mode: false, count: 0 });
    apiMocks.saveSettings.mockResolvedValue({ ok: true, updated: 0, message: '' });
    apiMocks.deleteSettingsKeys.mockResolvedValue({ ok: true, deleted: 0 });
  });

  afterEach(() => {
    vi.clearAllMocks();
    useUiStore.setState({ pinModalVisible: false });
  });

  it('drops the revoked bearer and asks for re-login when the server revokes sessions', async () => {
    window.sessionStorage.setItem(TOKEN_KEY, 'pre-revocation-token');
    apiMocks.changeAccessPin.mockResolvedValue({
      ok: true,
      detail: 'PIN updated. All sessions were revoked; sign in again.',
      reauthRequired: true,
      epoch: 4,
    });

    await renderLoadedPage();
    await submitPinChange();

    await waitFor(() => expect(apiMocks.changeAccessPin).toHaveBeenCalledWith('0000', '1234'));
    await waitFor(() => expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull());
    expect(useUiStore.getState().pinModalVisible).toBe(true);
    expect(screen.getByTestId('settings-pin-status')).toHaveTextContent(/다시 로그인/);
  });

  it('keeps the credential when the response says no re-auth is required', async () => {
    window.sessionStorage.setItem(TOKEN_KEY, 'still-valid-token');
    apiMocks.changeAccessPin.mockResolvedValue({
      ok: true,
      detail: 'PIN updated.',
      reauthRequired: false,
      epoch: 1,
    });

    await renderLoadedPage();
    await submitPinChange();

    await waitFor(() => expect(screen.getByTestId('settings-pin-status')).toHaveTextContent(/PIN updated/));
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe('still-valid-token');
    expect(useUiStore.getState().pinModalVisible).toBe(false);
  });

  it('never writes PIN values to browser storage on the revocation path', async () => {
    apiMocks.changeAccessPin.mockResolvedValue({
      ok: true,
      detail: 'PIN updated. All sessions were revoked; sign in again.',
      reauthRequired: true,
      epoch: 2,
    });

    await renderLoadedPage();
    await submitPinChange();

    await waitFor(() => expect(useUiStore.getState().pinModalVisible).toBe(true));
    expect(JSON.stringify(window.sessionStorage)).not.toContain('1234');
    expect(JSON.stringify(window.localStorage)).not.toContain('1234');
  });

  it('surfaces a failed change without clearing the credential', async () => {
    window.sessionStorage.setItem(TOKEN_KEY, 'still-valid-token');
    apiMocks.changeAccessPin.mockRejectedValue(new Error('HTTP 500: Internal Server Error'));

    await renderLoadedPage();
    await submitPinChange();

    await waitFor(() => expect(screen.getByTestId('settings-pin-status')).toHaveTextContent(/PIN 변경 실패/));
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe('still-valid-token');
    expect(useUiStore.getState().pinModalVisible).toBe(false);
  });
});
