// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import { createAccessPinHeaders } from './accessPinCredential';

describe('createAccessPinHeaders', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('does not invent a predictable PIN when no credential is stored', () => {
    const headers = createAccessPinHeaders({ 'Content-Type': 'application/json' });

    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.has('X-Access-Pin')).toBe(false);
  });

  it('adds the explicitly stored PIN', () => {
    window.localStorage.setItem('ag_access_pin', 'operator-secret');

    const headers = createAccessPinHeaders();

    expect(headers.get('X-Access-Pin')).toBe('operator-secret');
  });
});
