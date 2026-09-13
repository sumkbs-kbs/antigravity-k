import { afterEach, describe, expect, it } from 'vitest';
import {
  LEGACY_SETTINGS_STORAGE_KEY,
  SETTINGS_STORAGE_KEY,
  readBrowserSettings,
  sanitizeLegacyBrowserSettings,
  writeBrowserSettings,
} from './browserSettings';

const SECRET = 'sk-cr05-legacy-fake-9f2c-should-be-removed';

function raw(key: string): string | null {
  return window.localStorage.getItem(key);
}

describe('browserSettings', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('keeps only allowlisted non-secret preferences', () => {
    const count = writeBrowserSettings({
      default_model: 'model-x',
      // allowlist 밖(비밀) — 타입이 없으므로 캐스팅으로 우회 시도.
      ...({ OPENAI_API_KEY: SECRET, mcp_token: SECRET } as Record<string, string>),
    });

    expect(count).toBe(1);
    expect(raw(SETTINGS_STORAGE_KEY)).toContain('model-x');
    expect(raw(SETTINGS_STORAGE_KEY)).not.toContain(SECRET);
    expect(raw(SETTINGS_STORAGE_KEY)).not.toContain('OPENAI_API_KEY');
  });

  it('removes the stored key entirely when nothing survives the filter', () => {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({ OPENAI_API_KEY: SECRET }));

    const count = writeBrowserSettings({});

    expect(count).toBe(0);
    expect(raw(SETTINGS_STORAGE_KEY)).toBeNull();
    expect(raw(LEGACY_SETTINGS_STORAGE_KEY)).toBeNull();
  });

  it('sanitizes both legacy keys and is idempotent', () => {
    window.localStorage.setItem(
      SETTINGS_STORAGE_KEY,
      JSON.stringify({ OPENAI_API_KEY: SECRET, default_model: 'from-v1' }),
    );
    window.localStorage.setItem(
      LEGACY_SETTINGS_STORAGE_KEY,
      JSON.stringify({ GEMINI_API_KEY: SECRET, search_engine: 'jina' }),
    );

    const first = sanitizeLegacyBrowserSettings();

    expect(first.storageAvailable).toBe(true);
    expect(first.removedKeys).toEqual(['GEMINI_API_KEY', 'OPENAI_API_KEY']);
    expect(raw(SETTINGS_STORAGE_KEY)).not.toContain(SECRET);
    expect(raw(LEGACY_SETTINGS_STORAGE_KEY)).toBeNull();
    // 비밀이 아닌 preference는 살아남는다.
    const surviving = readBrowserSettings();
    expect(surviving.default_model).toBe('from-v1');
    expect(surviving.search_engine).toBe('jina');

    const second = sanitizeLegacyBrowserSettings();

    expect(second.removedKeys).toEqual([]);
    expect(raw(SETTINGS_STORAGE_KEY)).not.toContain(SECRET);
  });

  it('survives corrupt JSON without throwing', () => {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, '{not-json');
    window.localStorage.setItem(LEGACY_SETTINGS_STORAGE_KEY, '[]');

    expect(() => sanitizeLegacyBrowserSettings()).not.toThrow();
    expect(readBrowserSettings()).toEqual({});
  });

  it('reports unavailable storage instead of throwing when access is denied', () => {
    const denied = {
      getItem: () => { throw new Error('SecurityError'); },
      setItem: () => { throw new Error('SecurityError'); },
      removeItem: () => { throw new Error('SecurityError'); },
      clear: () => { throw new Error('SecurityError'); },
      key: () => null,
      length: 0,
    } as unknown as Storage;

    expect(sanitizeLegacyBrowserSettings(denied)).toEqual({
      removedKeys: [],
      keptKeys: [],
      storageAvailable: false,
    });
    expect(readBrowserSettings(denied)).toEqual({});
    expect(writeBrowserSettings({ default_model: 'x' }, denied)).toBe(0);
  });

  it('falls back to the legacy key when the v1 key is absent', () => {
    window.localStorage.setItem(LEGACY_SETTINGS_STORAGE_KEY, JSON.stringify({ search_engine: 'duckduckgo' }));

    expect(readBrowserSettings().search_engine).toBe('duckduckgo');
  });

  it('drops non-string values and empty strings', () => {
    window.localStorage.setItem(
      SETTINGS_STORAGE_KEY,
      JSON.stringify({ default_model: 'ok-model', search_engine: 7, daily_budget_usd: '' }),
    );

    expect(readBrowserSettings()).toEqual({ default_model: 'ok-model' });
  });
});
