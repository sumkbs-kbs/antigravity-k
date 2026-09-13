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
  // CR-06: 페이지가 401을 PIN 안내로 연결할 때 쓰는 판별 함수.
  isAuthRequiredError: vi.fn(() => false),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/shared/CacheStatsPanel', () => ({ default: () => <div /> }));
vi.mock('../components/shared/McpHealthCachePanel', () => ({ default: () => <div /> }));
vi.mock('../components/shared/McpOAuthPanel', () => ({ default: () => <div /> }));
vi.mock('../components/shared/ModelOperationsPanel', () => ({ default: () => <div /> }));

import SettingsPage from './SettingsPage';

const STORAGE_KEY = 'agk_user_settings:v1';
const SECRET = 'sk-cr05-fake-key-4a91bc-should-not-persist';

function storedSettings(): Record<string, unknown> {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
}

function keyInput(provider: string): HTMLInputElement {
  return screen.getByTestId(`api-key-input-${provider}`) as HTMLInputElement;
}

async function renderLoadedPage(): Promise<void> {
  render(<SettingsPage />);
  await waitFor(() => expect(screen.getByText('시스템 설정')).toBeInTheDocument());
}

async function clickSave(): Promise<void> {
  fireEvent.click(await screen.findByRole('button', { name: /설정 저장/ }));
}

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.clear();
    apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'model-a', provider: 'openrouter' } });
    apiMocks.fetchLogLevels.mockResolvedValue({ ok: true, loggers: [], debug_mode: false, count: 0 });
    apiMocks.saveSettings.mockResolvedValue({ ok: true, updated: 1, message: 'saved' });
    apiMocks.deleteSettingsKeys.mockResolvedValue({ ok: true, deleted: 1 });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('recovers from corrupt stored settings and loads the server configuration', async () => {
    localStorage.setItem('agk_user_settings', '{not-json');

    await renderLoadedPage();

    expect(screen.getByDisplayValue('model-a')).toBeInTheDocument();
    expect(apiMocks.fetchSettings).toHaveBeenCalledOnce();
  });

  it('reports a server failure without claiming a local save', async () => {
    apiMocks.saveSettings.mockRejectedValue(new Error('HTTP 503: Unavailable'));
    await renderLoadedPage();

    fireEvent.change(keyInput('OPENAI_API_KEY'), { target: { value: SECRET } });
    await clickSave();

    await waitFor(() => expect(screen.getByText(/서버 저장 실패/)).toBeInTheDocument());
    expect(screen.queryByText(/localStorage에 저장됨/)).not.toBeInTheDocument();
    expect(localStorage.getItem(STORAGE_KEY) ?? '').not.toContain(SECRET);
  });

  it('never persists a typed API key to browser storage', async () => {
    await renderLoadedPage();

    fireEvent.change(keyInput('OPENAI_API_KEY'), { target: { value: SECRET } });
    await clickSave();

    await waitFor(() => expect(apiMocks.saveSettings).toHaveBeenCalledOnce());
    for (const key of ['agk_user_settings:v1', 'agk_user_settings']) {
      expect(localStorage.getItem(key) ?? '').not.toContain(SECRET);
    }
    expect(JSON.stringify(storedSettings())).not.toContain(SECRET);
    expect(Object.keys(storedSettings())).not.toContain('OPENAI_API_KEY');
  });

  it('keeps non-secret preferences in browser storage', async () => {
    await renderLoadedPage();

    fireEvent.change(screen.getByDisplayValue('model-a'), { target: { value: 'model-b' } });
    await clickSave();

    await waitFor(() => expect(storedSettings()['default_model']).toBe('model-b'));
    expect(storedSettings()['search_engine']).toBe('searxng');
    expect(storedSettings()['hourly_action_limit']).toBe('100');
  });

  it('omits empty inputs so existing server keys are kept', async () => {
    apiMocks.fetchSettings.mockResolvedValue({
      model: { name: 'model-a' },
      api_keys_configured: { OPENAI_API_KEY: true, GEMINI_API_KEY: false },
    });
    await renderLoadedPage();

    await clickSave();

    // 보낼 키 변경이 없으면 권한이 필요한 서버 호출을 하지 않는다.
    expect(apiMocks.saveSettings).not.toHaveBeenCalled();
    expect(apiMocks.deleteSettingsKeys).not.toHaveBeenCalled();
    expect(screen.getByText(/API 키 변경 없음/)).toBeInTheDocument();
  });

  it('shows configured state from the server, never a masked value', async () => {
    apiMocks.fetchSettings.mockResolvedValue({
      model: { name: 'model-a' },
      api_keys_configured: { OPENAI_API_KEY: true, GEMINI_API_KEY: false },
    });

    await renderLoadedPage();

    expect(keyInput('OPENAI_API_KEY').value).toBe('');
    expect(keyInput('OPENAI_API_KEY').placeholder).toContain('••••••••');
    expect(keyInput('GEMINI_API_KEY').placeholder).toBe('API 키 입력');
    // 설정된 provider 옆에 삭제 버튼이 있고, 미설정 provider에는 없다.
    expect(screen.getByTestId('api-key-delete-OPENAI_API_KEY')).toBeInTheDocument();
    expect(screen.queryByTestId('api-key-delete-GEMINI_API_KEY')).not.toBeInTheDocument();
  });

  it('clears the input and refreshes configured state after a successful save', async () => {
    apiMocks.fetchSettings
      .mockResolvedValueOnce({ model: { name: 'model-a' }, api_keys_configured: {} })
      .mockResolvedValueOnce({ model: { name: 'model-a' }, api_keys_configured: { OPENAI_API_KEY: true } });

    await renderLoadedPage();
    fireEvent.change(keyInput('OPENAI_API_KEY'), { target: { value: SECRET } });
    await clickSave();

    await waitFor(() => expect(screen.getByText(/저장 완료/)).toBeInTheDocument());
    expect(keyInput('OPENAI_API_KEY').value).toBe('');
    expect(screen.getByTestId('api-key-delete-OPENAI_API_KEY')).toBeInTheDocument();
  });

  it('deletes a key only through the explicit delete action', async () => {
    apiMocks.fetchSettings
      .mockResolvedValueOnce({ model: { name: 'model-a' }, api_keys_configured: { OPENAI_API_KEY: true } })
      .mockResolvedValueOnce({ model: { name: 'model-a' }, api_keys_configured: {} });

    await renderLoadedPage();
    fireEvent.click(screen.getByTestId('api-key-delete-OPENAI_API_KEY'));
    await clickSave();

    await waitFor(() => expect(apiMocks.deleteSettingsKeys).toHaveBeenCalledWith(['OPENAI_API_KEY']));
    expect(apiMocks.saveSettings).not.toHaveBeenCalled();
    expect(screen.queryByTestId('api-key-delete-OPENAI_API_KEY')).not.toBeInTheDocument();
  });

  it('lets the user cancel a pending deletion before saving', async () => {
    apiMocks.fetchSettings.mockResolvedValue({
      model: { name: 'model-a' },
      api_keys_configured: { OPENAI_API_KEY: true },
    });

    await renderLoadedPage();
    fireEvent.click(screen.getByTestId('api-key-delete-OPENAI_API_KEY'));
    expect(screen.getByTestId('api-key-undo-OPENAI_API_KEY')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('api-key-undo-OPENAI_API_KEY'));
    await clickSave();

    expect(apiMocks.deleteSettingsKeys).not.toHaveBeenCalled();
    expect(screen.getByTestId('api-key-delete-OPENAI_API_KEY')).toBeInTheDocument();
  });

  it('does not hydrate API keys found in legacy browser storage', async () => {
    localStorage.setItem(
      'agk_user_settings:v1',
      JSON.stringify({ OPENAI_API_KEY: SECRET, default_model: 'legacy-model' }),
    );

    await renderLoadedPage();

    expect(keyInput('OPENAI_API_KEY').value).toBe('');
    // CR-06: 기본 모델은 서버 관리 값이라 브라우저의 오래된 값이 덮어쓰지 않는다.
    expect(screen.getByDisplayValue('model-a')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('legacy-model')).not.toBeInTheDocument();
  });
});
