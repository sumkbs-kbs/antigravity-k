/**
 * SettingsPage · CR-08 provider 접근성 이름
 * ==========================================
 * BASELINE F04-a: "SettingsPage.tsx provider 입력 label 연결 없음".
 *
 * 수정 전에는 여섯 provider 비밀 입력의 접근성 이름이 placeholder('API 키 입력')로
 * 모두 같아 화면 낭독으로 구분할 수 없었다. 지금은 보이는 provider 이름이
 * aria-labelledby로 연결되어 각 입력이 고유한 이름을 갖는다.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

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

const PROVIDER_KEYS = [
  'OPENROUTER_API_KEY',
  'NVIDIA_API_KEY',
  'OPENAI_API_KEY',
  'GEMINI_API_KEY',
  'ZAI_API_KEY',
  'ANTHROPIC_API_KEY',
] as const;

async function renderPage(): Promise<void> {
  render(<SettingsPage />);
  await waitFor(() => expect(screen.getByText('시스템 설정')).toBeInTheDocument());
}

function keyInput(key: string): HTMLInputElement {
  return screen.getByTestId(`api-key-input-${key}`) as HTMLInputElement;
}

beforeEach(() => {
  localStorage.clear();
  apiMocks.fetchSettings.mockResolvedValue({ model: { name: 'model-a', provider: 'openrouter' } });
  apiMocks.fetchLogLevels.mockResolvedValue({ ok: true, loggers: [], debug_mode: false, count: 0 });
  apiMocks.saveSettings.mockResolvedValue({ ok: true, updated: 0, message: 'saved' });
  apiMocks.changeAccessPin.mockResolvedValue({ ok: true, detail: 'PIN updated.' });
    apiMocks.deleteSettingsKeys.mockResolvedValue({ ok: true, deleted: 0 });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('SettingsPage · CR-08 provider 접근성 이름', () => {
  it('모든 provider 비밀 입력이 이름 연결을 갖는다', async () => {
    await renderPage();

    for (const key of PROVIDER_KEYS) {
      const input = keyInput(key);
      const labelled = (input.getAttribute('aria-labelledby') ?? '').trim();
      expect(labelled, `${key}: aria-labelledby 누락`).not.toBe('');
      expect(document.getElementById(labelled.split(/\s+/)[0]), `${key}: 라벨 대상 미존재`).not.toBeNull();
    }
  });

  it('provider별 접근성 이름이 서로 다르고 자기 provider를 담는다', async () => {
    await renderPage();

    const labels = PROVIDER_KEYS.map(key =>
      (document.getElementById(`api-key-label-${key}`)?.textContent ?? '').trim(),
    );

    // 이름이 비어 있지 않고 서로 다르다(수정 전에는 여섯 개가 같은 placeholder 이름이었다).
    expect(labels.every(label => label.length > 0)).toBe(true);
    expect(new Set(labels).size).toBe(PROVIDER_KEYS.length);

    // 각 이름이 정확히 자기 입력을 가리킨다.
    labels.forEach((label, index) => {
      expect(screen.getByLabelText(label), `${PROVIDER_KEYS[index]} 이름이 다른 입력을 가리킨다`)
        .toBe(keyInput(PROVIDER_KEYS[index]));
    });
  });

  it('provider 이름에 브랜드가 들어 있어 낭독으로 구분할 수 있다', async () => {
    await renderPage();

    const brands: Array<[string, RegExp]> = [
      ['OPENROUTER_API_KEY', /openrouter/i],
      ['NVIDIA_API_KEY', /nvidia/i],
      ['OPENAI_API_KEY', /openai/i],
      ['GEMINI_API_KEY', /gemini/i],
      ['ZAI_API_KEY', /zhipu/i],
      ['ANTHROPIC_API_KEY', /anthropic/i],
    ];

    for (const [key, brand] of brands) {
      expect(screen.getByLabelText(brand)).toBe(keyInput(key));
    }
  });

  it('이름 연결이 추가돼도 비밀 입력은 여전히 브라우저에 저장되지 않는다', async () => {
    await renderPage();

    const input = keyInput('OPENAI_API_KEY');
    expect(input.type).toBe('password');

    input.value = 'sk-cr08-should-not-persist';
    input.dispatchEvent(new Event('input', { bubbles: true }));

    const stored = Object.keys(localStorage).filter(storageKey => storageKey.startsWith('agk_user_settings'));
    stored.forEach(storageKey => {
      expect(localStorage.getItem(storageKey) ?? '').not.toContain('sk-cr08-should-not-persist');
    });
  });
});
