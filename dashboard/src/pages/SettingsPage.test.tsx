import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const apiMocks = vi.hoisted(() => ({
  fetchSettings: vi.fn(),
  saveSettings: vi.fn(),
  fetchLogLevels: vi.fn(),
  setLogLevel: vi.fn(),
  setAllLogLevels: vi.fn(),
  setDebugMode: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);
vi.mock('../components/shared/CacheStatsPanel', () => ({ default: () => <div /> }));
vi.mock('../components/shared/ModelOperationsPanel', () => ({ default: () => <div /> }));

import SettingsPage from './SettingsPage';

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.clear();
    apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'model-a', provider: 'openrouter' } });
    apiMocks.fetchLogLevels.mockResolvedValue({ ok: true, loggers: [], debug_mode: false, count: 0 });
    apiMocks.saveSettings.mockResolvedValue({ ok: true, updated: 1, message: 'saved' });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('recovers from corrupt stored settings and loads the server configuration', async () => {
    localStorage.setItem('agk_user_settings', '{not-json');

    render(<SettingsPage />);

    await waitFor(() => expect(screen.getByText('시스템 설정')).toBeInTheDocument());
    expect(screen.getByDisplayValue('model-a')).toBeInTheDocument();
    expect(apiMocks.fetchSettings).toHaveBeenCalledOnce();
  });

  it('shows a synchronization failure when saving settings is rejected', async () => {
    apiMocks.saveSettings.mockRejectedValue(new Error('HTTP 503: Unavailable'));
    render(<SettingsPage />);

    const saveButton = await screen.findByRole('button', { name: /설정 저장/ });
    fireEvent.click(saveButton);

    await waitFor(() => expect(screen.getByText(/localStorage에 저장됨/)).toBeInTheDocument());
    expect(apiMocks.saveSettings).toHaveBeenCalledOnce();
  });
});
