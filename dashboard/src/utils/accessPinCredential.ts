const ACCESS_PIN_KEY = 'ag_access_pin';

function accessPinCookie(value: string, maxAge: number): string {
  const secure = typeof window !== 'undefined' && window.location.protocol === 'https:'
    ? '; Secure'
    : '';
  return `${ACCESS_PIN_KEY}=${value}; path=/; max-age=${maxAge}; SameSite=Strict${secure}`;
}

export function readStoredAccessPin(): string | null {
  if (typeof window === 'undefined') return null;

  try {
    const pin = window.localStorage.getItem(ACCESS_PIN_KEY)?.trim() ?? '';
    return pin.length > 0 ? pin : null;
  } catch {
    return null;
  }
}

export function createAccessPinHeaders(initial?: HeadersInit): Headers {
  const headers = new Headers(initial);
  const pin = readStoredAccessPin();
  if (pin !== null) headers.set('X-Access-Pin', pin);
  return headers;
}

export function persistAccessPin(pin: string): void {
  window.localStorage.setItem(ACCESS_PIN_KEY, pin);
  document.cookie = accessPinCookie(pin, 31_536_000);
}

export function clearAccessPin(): void {
  try {
    window.localStorage.removeItem(ACCESS_PIN_KEY);
  } finally {
    document.cookie = accessPinCookie('', 0);
  }
}
