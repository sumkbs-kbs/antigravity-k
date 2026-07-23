/**
 * Vitest Setup
 * =============
 * Global test configuration: jsdom environment, mocks for browser APIs
 * that aren't available in jsdom (ResizeObserver, matchMedia, etc.).
 */

import '@testing-library/jest-dom';

/* ─── ResizeObserver Mock ──────────────────────────────────── */
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

/* ─── matchMedia Mock ──────────────────────────────────────── */
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

/* ─── scrollIntoView Mock ──────────────────────────────────── */
Element.prototype.scrollIntoView = () => {};

/* ─── localStorage Mock ────────────────────────────────────── */
const store: Record<string, string> = {};
const localStorageMock: Storage = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => { store[key] = value; },
  removeItem: (key: string) => { delete store[key]; },
  clear: () => { Object.keys(store).forEach(k => delete store[k]); },
  get length() { return Object.keys(store).length; },
  key: (index: number) => Object.keys(store)[index] ?? null,
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });
