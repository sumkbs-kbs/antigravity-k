/**
 * Publish History Tests
 * ======================
 * Unit tests for publish history utility functions:
 * - loadHistory: localStorage read + JSON parse + validation
 * - saveHistory: localStorage write + MAX_HISTORY cap
 * - buildEntry: PublishResult → PublishHistoryEntry conversion
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { loadHistory, saveHistory, buildEntry, HISTORY_KEY, MAX_HISTORY } from '../PublishTab';
import type { PublishResult } from '../types';

/* ─── Helpers ───────────────────────────────────────────────── */

function result(overrides: Partial<PublishResult> = {}): PublishResult {
  return {
    success: true,
    action: 'npm_publish',
    skill_name: 'test-skill',
    package_name: '@antigravity-k/skill-test-skill',
    version: '1.0.0',
    npm_url: 'https://www.npmjs.com/package/@antigravity-k/skill-test-skill',
    pr_url: '',
    errors: [],
    warnings: [],
    summary: '✅ @antigravity-k/skill-test-skill@1.0.0 npm publish 완료',
    ...overrides,
  };
}

/* ─── loadHistory ───────────────────────────────────────────── */

describe('loadHistory', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns empty array when nothing is stored', () => {
    const entries = loadHistory();
    expect(entries).toEqual([]);
  });

  it('returns parsed array when valid JSON is stored', () => {
    const data = [
      { id: '1', skill_name: 'test', action: 'npm_publish', success: true, timestamp: '2026-07-21T12:00:00Z', dry_run: true, summary: 'ok', errors: [], warnings: [] },
    ];
    localStorage.setItem(HISTORY_KEY, JSON.stringify(data));

    const entries = loadHistory();
    expect(entries).toHaveLength(1);
    expect(entries[0].skill_name).toBe('test');
    expect(entries[0].success).toBe(true);
  });

  it('returns empty array when stored value is not an array', () => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify({ not: 'an array' }));
    expect(loadHistory()).toEqual([]);
  });

  it('returns empty array when stored value is a string', () => {
    localStorage.setItem(HISTORY_KEY, '"just a string"');
    expect(loadHistory()).toEqual([]);
  });

  it('returns empty array when stored value is a number', () => {
    localStorage.setItem(HISTORY_KEY, '42');
    expect(loadHistory()).toEqual([]);
  });

  it('returns empty array when key does not exist', () => {
    expect(loadHistory()).toEqual([]);
  });

  it('returns empty array when stored value is corrupted JSON', () => {
    localStorage.setItem(HISTORY_KEY, '{corrupted');
    expect(loadHistory()).toEqual([]);
  });

  it('preserves all fields in stored entries', () => {
    const entry = {
      id: 'entry_1',
      skill_name: 'my-skill',
      action: 'github_pr' as const,
      success: false,
      timestamp: '2026-07-21T14:30:00Z',
      version: '2.0.0',
      package_name: '@antigravity-k/skill-my-skill',
      dry_run: false,
      summary: '❌ my-skill publish 실패',
      errors: ['npm publish failed'],
      warnings: ['README.md missing'],
      npm_url: '',
      pr_url: 'https://github.com/org/repo/pull/1',
    };
    localStorage.setItem(HISTORY_KEY, JSON.stringify([entry]));

    const [loaded] = loadHistory();
    expect(loaded).toEqual(entry);
  });
});

/* ─── saveHistory ───────────────────────────────────────────── */

describe('saveHistory', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('saves entries to localStorage', () => {
    const entries = [
      { id: '1', skill_name: 'test', action: 'npm_publish' as const, success: true, timestamp: '2026-07-21T12:00:00Z', dry_run: true, summary: 'ok', errors: [], warnings: [] },
    ];
    saveHistory(entries);

    const raw = localStorage.getItem(HISTORY_KEY);
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].skill_name).toBe('test');
  });

  it('truncates to MAX_HISTORY entries', () => {
    const manyEntries = Array.from({ length: MAX_HISTORY + 20 }, (_, i) => ({
      id: `${i}`,
      skill_name: `skill-${i}`,
      action: 'npm_publish' as const,
      success: true,
      timestamp: new Date().toISOString(),
      dry_run: true,
      summary: 'ok',
      errors: [] as string[],
      warnings: [] as string[],
    }));

    saveHistory(manyEntries);

    const raw = localStorage.getItem(HISTORY_KEY);
    const parsed = JSON.parse(raw!);
    expect(parsed).toHaveLength(MAX_HISTORY);
    // Should keep the first MAX_HISTORY items (newest)
    expect(parsed[0].id).toBe('0');
    expect(parsed[MAX_HISTORY - 1].id).toBe(String(MAX_HISTORY - 1));
  });

  it('overwrites existing data', () => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify([{ id: 'old', skill_name: 'old', action: 'npm_publish', success: true, timestamp: '', dry_run: false, summary: '', errors: [], warnings: [] }]));

    const newEntries = [
      { id: 'new', skill_name: 'new', action: 'github_pr' as const, success: false, timestamp: '2026-07-21T12:00:00Z', dry_run: false, summary: '', errors: [] as string[], warnings: [] as string[] },
    ];
    saveHistory(newEntries);

    const loaded = loadHistory();
    expect(loaded).toHaveLength(1);
    expect(loaded[0].id).toBe('new');
  });

  it('handles empty array', () => {
    saveHistory([]);
    const loaded = loadHistory();
    expect(loaded).toEqual([]);
  });

  it('does not throw when localStorage is full', () => {
    // Mock localStorage.setItem to throw
    const orig = localStorage.setItem;
    localStorage.setItem = () => { throw new Error('QuotaExceededError'); };

    const entries = [
      { id: '1', skill_name: 'test', action: 'npm_publish' as const, success: true, timestamp: '', dry_run: false, summary: '', errors: [] as string[], warnings: [] as string[] },
    ];
    expect(() => saveHistory(entries)).not.toThrow();

    localStorage.setItem = orig;
  });
});

/* ─── buildEntry ────────────────────────────────────────────── */

describe('buildEntry', () => {
  it('generates an id with pub_ prefix', () => {
    const entry = buildEntry(result(), false);
    expect(entry.id).toMatch(/^pub_\d+_[a-z0-9]{6}$/);
  });

  it('generates unique ids for successive calls', () => {
    const a = buildEntry(result(), false);
    const b = buildEntry(result(), false);
    expect(a.id).not.toBe(b.id);
  });

  it('sets timestamp to current ISO string', () => {
    const before = Date.now();
    const entry = buildEntry(result(), false);
    const after = Date.now();

    const ts = new Date(entry.timestamp).getTime();
    expect(ts).toBeGreaterThanOrEqual(before - 100);
    expect(ts).toBeLessThanOrEqual(after + 100);
  });

  it('copies all fields from success npm publish result', () => {
    const r = result();
    const entry = buildEntry(r, false);

    expect(entry.skill_name).toBe('test-skill');
    expect(entry.action).toBe('npm_publish');
    expect(entry.success).toBe(true);
    expect(entry.version).toBe('1.0.0');
    expect(entry.package_name).toBe('@antigravity-k/skill-test-skill');
    expect(entry.dry_run).toBe(false);
    expect(entry.summary).toContain('✅');
    expect(entry.errors).toEqual([]);
    expect(entry.warnings).toEqual([]);
    expect(entry.npm_url).toBe('https://www.npmjs.com/package/@antigravity-k/skill-test-skill');
    expect(entry.pr_url).toBe('');
  });

  it('copies all fields from failed GitHub PR result', () => {
    const r = result({
      success: false,
      action: 'github_pr',
      skill_name: 'broken-skill',
      pr_url: 'https://github.com/org/repo/pull/42',
      errors: ['PR creation failed'],
      warnings: ['gh CLI not found'],
      summary: '❌ broken-skill GitHub PR 실패',
    });
    const entry = buildEntry(r, true);

    expect(entry.skill_name).toBe('broken-skill');
    expect(entry.action).toBe('github_pr');
    expect(entry.success).toBe(false);
    expect(entry.dry_run).toBe(true);
    expect(entry.errors).toEqual(['PR creation failed']);
    expect(entry.warnings).toEqual(['gh CLI not found']);
    expect(entry.pr_url).toBe('https://github.com/org/repo/pull/42');
    expect(entry.npm_url).toBe('https://www.npmjs.com/package/@antigravity-k/skill-test-skill');
  });

  it('sets dry_run flag correctly when true', () => {
    const entry = buildEntry(result(), true);
    expect(entry.dry_run).toBe(true);
  });

  it('sets dry_run flag correctly when false', () => {
    const entry = buildEntry(result(), false);
    expect(entry.dry_run).toBe(false);
  });

  it('handles missing optional fields gracefully', () => {
    const r = result({
      version: undefined,
      package_name: undefined,
      npm_url: undefined,
      pr_url: undefined,
    });
    const entry = buildEntry(r, false);

    expect(entry.version).toBeUndefined();
    expect(entry.package_name).toBeUndefined();
    expect(entry.npm_url).toBeUndefined();
    expect(entry.pr_url).toBeUndefined();
  });

  it('handles special characters in skill name', () => {
    const r = result({ skill_name: 'skill-with-unicode-🔧' });
    const entry = buildEntry(r, false);
    expect(entry.skill_name).toBe('skill-with-unicode-🔧');
  });

  it('stores empty arrays for no errors/warnings', () => {
    const entry = buildEntry(result(), false);
    expect(entry.errors).toEqual([]);
    expect(entry.warnings).toEqual([]);
  });
});

/* ─── Integration: save then load roundtrip ─────────────────── */

describe('publish history roundtrip', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('roundtrips a single entry', () => {
    const r = result();
    const entry = buildEntry(r, true);

    saveHistory([entry]);
    const loaded = loadHistory();

    expect(loaded).toHaveLength(1);
    expect(loaded[0].id).toBe(entry.id);
    expect(loaded[0].skill_name).toBe('test-skill');
    expect(loaded[0].success).toBe(true);
    expect(loaded[0].dry_run).toBe(true);
  });

  it('roundtrips multiple entries preserving order', () => {
    const entries = [1, 2, 3].map(i =>
      buildEntry(result({ skill_name: `skill-${i}`, success: i % 2 === 0 }), i % 2 === 0),
    );

    saveHistory(entries);
    const loaded = loadHistory();

    expect(loaded).toHaveLength(3);
    expect(loaded[0].skill_name).toBe('skill-1');
    expect(loaded[1].skill_name).toBe('skill-2');
    expect(loaded[2].skill_name).toBe('skill-3');
    expect(loaded[0].success).toBe(false);
    expect(loaded[1].success).toBe(true);
  });

  it('enforces MAX_HISTORY on roundtrip with overflow', () => {
    const overflow = Array.from({ length: MAX_HISTORY + 10 }, (_, i) =>
      buildEntry(result({ skill_name: `skill-${i}` }), false),
    );

    saveHistory(overflow);
    const loaded = loadHistory();
    expect(loaded).toHaveLength(MAX_HISTORY);
  });

  it('multiple saves append and cap correctly', () => {
    // First batch: fill to MAX_HISTORY - 5
    const batch1 = Array.from({ length: MAX_HISTORY - 5 }, (_, i) =>
      buildEntry(result({ skill_name: `batch1-${i}` }), false),
    );
    saveHistory(batch1);
    expect(loadHistory()).toHaveLength(MAX_HISTORY - 5);

    // Second batch: add 10 more, should cap at MAX_HISTORY
    const batch2 = Array.from({ length: 10 }, (_, i) =>
      buildEntry(result({ skill_name: `batch2-${i}` }), false),
    );
    saveHistory([...batch2, ...loadHistory()]);
    expect(loadHistory()).toHaveLength(MAX_HISTORY);
  });

  it('clears state via localStorage.removeItem', () => {
    const entry = buildEntry(result(), false);
    saveHistory([entry]);
    expect(loadHistory()).toHaveLength(1);

    localStorage.removeItem(HISTORY_KEY);
    expect(loadHistory()).toHaveLength(0);
  });
});
