/**
 * browserSettings — 브라우저에 남겨도 되는 설정만 다룬다 (CR-05).
 * =================================================================
 * 발견 F01: 설정 화면이 API 키를 localStorage에 **원문**으로 저장했다
 * (`agk_user_settings:v1`). 이 모듈은 저장 계층의 유일한 진입점이 되어
 *  1) 저장 가능 키를 allowlist(비밀 아님)로 제한하고,
 *  2) 앱 시작 시 예전에 남은 키를 idempotent하게 정화하고,
 *  3) localStorage 접근 불가/잘못된 JSON에서도 앱을 중단시키지 않는다.
 *
 * API 키는 여기로 오지 않는다. 키는 입력 중에만 메모리에 존재하고 서버로만
 * 전송된다(sessionStorage/IndexedDB로 옮기는 것도 해결이 아니다).
 */

export const SETTINGS_STORAGE_KEY = 'agk_user_settings:v1';
export const LEGACY_SETTINGS_STORAGE_KEY = 'agk_user_settings';

/** 브라우저에 영속해도 되는 비밀 아닌 preference 목록. */
export const BROWSER_SETTING_KEYS = [
  'default_model',
  'search_engine',
  'daily_budget_usd',
  'hourly_action_limit',
] as const;

export type BrowserSettingKey = (typeof BROWSER_SETTING_KEYS)[number];
export type BrowserSettings = Partial<Record<BrowserSettingKey, string>>;

const BROWSER_SETTING_KEY_SET: ReadonlySet<string> = new Set<string>(BROWSER_SETTING_KEYS);

/** 값 이름에 비밀을 연상시키는 조각이 있는가(allowlist 밖 키 판정 보조). */
const SECRET_LIKE_PATTERN = /(_API_KEY|APIKEY|_TOKEN|TOKEN$|_SECRET|SECRET$|PASSWORD|_PIN$|PIN$)/i;

export function isBrowserSettingKey(key: string): key is BrowserSettingKey {
  return BROWSER_SETTING_KEY_SET.has(key);
}

export function isSecretLikeSettingKey(key: string): boolean {
  return SECRET_LIKE_PATTERN.test(key);
}

function safeStorage(storage?: Storage): Storage | null {
  if (storage) return storage;
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    // 접근 자체가 거부된 브라우저 설정(쿠키/스토리지 차단)에서도 앱은 살아야 한다.
    return null;
  }
}

function readJsonObject(storage: Storage | null, key: string): Record<string, unknown> | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    return value as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** allowlist 키 + 문자열 값만 남긴다. */
export function pickBrowserSettings(raw: Record<string, unknown> | null): BrowserSettings {
  const result: BrowserSettings = {};
  if (!raw) return result;
  for (const [key, value] of Object.entries(raw)) {
    if (!isBrowserSettingKey(key)) continue;
    if (typeof value === 'string' && value !== '') result[key] = value;
  }
  return result;
}

export function readBrowserSettings(storage?: Storage): BrowserSettings {
  const store = safeStorage(storage);
  if (!store) return {};
  const primary = readJsonObject(store, SETTINGS_STORAGE_KEY);
  if (primary) return pickBrowserSettings(primary);
  return pickBrowserSettings(readJsonObject(store, LEGACY_SETTINGS_STORAGE_KEY));
}

/**
 * allowlist 밖의 키는 조용히 버린다(저장 계층 방어). 남길 값이 없으면 키를 지운다.
 * @returns 실제로 저장된 키 개수
 */
export function writeBrowserSettings(values: BrowserSettings, storage?: Storage): number {
  const store = safeStorage(storage);
  if (!store) return 0;
  const sanitized = pickBrowserSettings(values as Record<string, unknown>);
  const count = Object.keys(sanitized).length;
  try {
    if (count === 0) {
      store.removeItem(SETTINGS_STORAGE_KEY);
      store.removeItem(LEGACY_SETTINGS_STORAGE_KEY);
      return 0;
    }
    store.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(sanitized));
    store.removeItem(LEGACY_SETTINGS_STORAGE_KEY);
  } catch {
    return 0;
  }
  return count;
}

export interface LegacySettingsSanitization {
  /** 비밀로 판정되어 제거된 키 **이름**(값은 절대 담지 않는다). */
  removedKeys: string[];
  /** 남은 비밀 아닌 preference 키. */
  keptKeys: string[];
  /** 정화 대상 저장소를 읽을 수 있었는가. */
  storageAvailable: boolean;
}

/**
 * 앱 시작 시 1회 호출하는 idempotent 정화.
 *
 * `agk_user_settings:v1` / `agk_user_settings` 두 키 모두에서 allowlist 밖 키
 * (예: `OPENAI_API_KEY`)를 제거하고, 남는 값이 없으면 키 자체를 지운다.
 * 잘못된 JSON이나 접근 거부는 예외 없이 "정화할 것이 없음"으로 처리한다.
 */
export function sanitizeLegacyBrowserSettings(storage?: Storage): LegacySettingsSanitization {
  const store = safeStorage(storage);
  if (!store) return { removedKeys: [], keptKeys: [], storageAvailable: false };

  const removed = new Set<string>();
  const kept = new Set<string>();

  try {
    // 접근 자체가 거부되면(getItem이 throw) 정화할 수 없다고 정직하게 알린다.
    store.getItem(SETTINGS_STORAGE_KEY);
    for (const key of [SETTINGS_STORAGE_KEY, LEGACY_SETTINGS_STORAGE_KEY]) {
      const raw = readJsonObject(store, key);
      if (!raw) continue;
      for (const candidate of Object.keys(raw)) {
        if (!isBrowserSettingKey(candidate)) removed.add(candidate);
      }
      for (const candidate of Object.keys(pickBrowserSettings(raw))) kept.add(candidate);
    }
  } catch {
    return { removedKeys: [], keptKeys: [], storageAvailable: false };
  }

  const merged = pickBrowserSettings({
    ...(readJsonObject(store, LEGACY_SETTINGS_STORAGE_KEY) ?? {}),
    ...(readJsonObject(store, SETTINGS_STORAGE_KEY) ?? {}),
  });
  writeBrowserSettings(merged, store);

  return {
    removedKeys: [...removed].sort(),
    keptKeys: [...kept].sort(),
    storageAvailable: true,
  };
}
