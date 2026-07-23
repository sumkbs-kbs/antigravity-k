/**
 * Tests for PublishTab — Skill Publishing Dashboard.
 *
 * Covers: loadHistory, saveHistory, buildEntry utility functions,
 * and the PublishTab component rendering (loading, empty, skill list).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { loadHistory, saveHistory, buildEntry, HISTORY_KEY, MAX_HISTORY } from '../PublishTab';
import type { PublishResult } from '../types';

// ─── Utility Functions ───────────────────────────────────────────

describe('loadHistory', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns empty array when no history exists', () => {
    expect(loadHistory()).toEqual([]);
  });

  it('returns parsed array from localStorage', () => {
    const entries = [{ id: 'pub_1', skill_name: 'test-skill' }];
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
    expect(loadHistory()).toEqual(entries);
  });

  it('returns empty array on invalid JSON', () => {
    localStorage.setItem(HISTORY_KEY, 'invalid json');
    expect(loadHistory()).toEqual([]);
  });

  it('returns empty array when stored value is not an array', () => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify({ not: 'array' }));
    expect(loadHistory()).toEqual([]);
  });
});

describe('saveHistory', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('saves entries to localStorage', () => {
    const entries = [{ id: 'pub_1', skill_name: 'test' }];
    saveHistory(entries);
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    expect(saved).toEqual(entries);
  });

  it('truncates to MAX_HISTORY', () => {
    const entries = Array.from({ length: 100 }, (_, i) => ({ id: `pub_${i}`, skill_name: `skill-${i}` }));
    saveHistory(entries);
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    expect(saved.length).toBe(MAX_HISTORY);
  });
});

describe('buildEntry', () => {
  it('builds entry from success result', () => {
    const result: PublishResult = {
      success: true,
      action: 'npm_publish',
      skill_name: 'my-skill',
      errors: [],
      warnings: [],
      summary: 'Published successfully',
      version: '1.0.0',
      package_name: '@test/my-skill',
      npm_url: 'https://npmjs.com/test/my-skill',
    };
    const entry = buildEntry(result, false);
    expect(entry.success).toBe(true);
    expect(entry.skill_name).toBe('my-skill');
    expect(entry.version).toBe('1.0.0');
    expect(entry.dry_run).toBe(false);
  });

  it('marks dry-run in entry', () => {
    const result: PublishResult = {
      success: true, action: 'npm_publish', skill_name: 'test', errors: [], warnings: [], summary: 'ok',
    };
    const entry = buildEntry(result, true);
    expect(entry.dry_run).toBe(true);
  });

  it('includes errors in entry', () => {
    const result: PublishResult = {
      success: false, action: 'npm_publish', skill_name: 'test', errors: ['Failed to publish'], warnings: [], summary: 'fail',
    };
    const entry = buildEntry(result, false);
    expect(entry.errors).toContain('Failed to publish');
  });
});

describe('PublishTab', () => {
  it('renders loading state initially', async () => {
    // Mock fetch to hang initially
    globalThis.fetch = vi.fn().mockImplementationOnce(() => new Promise(() => {}));

    const PublishTab = (await import('../PublishTab')).default;
    const { container } = render(<PublishTab />);
    // Should show loading message
    expect(container.textContent).toMatch(/불러오는 중/i);
  });

  it('renders empty state when no skills returned', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve({ skills: [] }),
    });

    const PublishTab = (await import('../PublishTab')).default;
    render(<PublishTab />);

    // Wait for loading to complete
    await act(async () => { await new Promise(r => setTimeout(r, 50)); });
    expect(screen.getByText(/로컬 스킬이 없습니다/i)).toBeInTheDocument();
  });

  it('renders skill cards when skills returned', async () => {
    const skills = [
      { name: 'test-skill', source: 'local', version: '1.0.0', tool_count: 3, warnings: [], valid: true },
    ];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve({ skills }),
    });

    const PublishTab = (await import('../PublishTab')).default;
    render(<PublishTab />);

    await act(async () => { await new Promise(r => setTimeout(r, 50)); });
    expect(screen.getByText(/test-skill/i)).toBeInTheDocument();
  });

  it('shows warning badges for skills with warnings', async () => {
    const skills = [
      { name: 'warn-skill', source: 'local', version: '1.0.0', tool_count: 1, warnings: ['Missing description'], valid: false },
    ];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve({ skills }),
    });

    const { default: PublishTab } = await import('../PublishTab');
    render(<PublishTab />);

    await act(async () => { await new Promise(r => setTimeout(r, 50)); });
    expect(screen.getByText(/Missing description/i)).toBeInTheDocument();
  });
});
