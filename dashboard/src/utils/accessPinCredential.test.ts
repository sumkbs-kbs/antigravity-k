// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  clearAccessCredential,
  createAccessPinHeaders,
  loginWithAccessPin,
  readLegacyAccessPin,
  readStoredAccessToken,
} from './accessPinCredential';

describe('createAccessPinHeaders', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it('does not invent a predictable PIN when no credential is stored', () => {
    const headers = createAccessPinHeaders({ 'Content-Type': 'application/json' });

    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.has('X-Access-Pin')).toBe(false);
  });

  it('adds the stored bearer token and never reads the legacy PIN', () => {
    window.localStorage.setItem('ag_access_pin', 'operator-secret');
    window.sessionStorage.setItem('ag_access_token', 'token-value');

    const headers = createAccessPinHeaders();

    expect(headers.get('Authorization')).toBe('Bearer token-value');
    expect(headers.has('X-Access-Pin')).toBe(false);
  });

  it('migrates a legacy PIN through login and stores only the returned token', async () => {
    window.localStorage.setItem('ag_access_pin', 'operator-secret');
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(
      JSON.stringify({ access_token: 'token-value', token_type: 'bearer', expires_in: 3600 }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ));
    vi.stubGlobal('fetch', fetchMock);

    await expect(loginWithAccessPin('operator-secret')).resolves.toBe('token-value');
    expect(fetchMock).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ pin: 'operator-secret' }),
    }));
    expect(readStoredAccessToken()).toBe('token-value');
    expect(readLegacyAccessPin()).toBeNull();
    expect(window.sessionStorage.getItem('ag_access_pin')).toBeNull();
    clearAccessCredential();
    vi.unstubAllGlobals();
  });
});
