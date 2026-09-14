import { describe, expect, it } from 'vitest';
import { resolveBackendTarget } from './vite.backendHealth';

describe('resolveBackendTarget', () => {
  it('defaults to loopback :8000 (never :8400)', () => {
    expect(resolveBackendTarget({})).toBe('http://127.0.0.1:8000');
    expect(resolveBackendTarget({})).not.toContain('8400');
  });

  it('prefers VITE_BACKEND_URL then AGK_BACKEND_URL', () => {
    expect(
      resolveBackendTarget({
        VITE_BACKEND_URL: 'http://127.0.0.1:9001/',
        AGK_BACKEND_URL: 'http://127.0.0.1:9002',
      }),
    ).toBe('http://127.0.0.1:9001');
    expect(
      resolveBackendTarget({
        AGK_BACKEND_URL: 'http://127.0.0.1:9002',
      }),
    ).toBe('http://127.0.0.1:9002');
  });
});
