/**
 * outputStore Tests
 * ==================
 * Tests for the Zustand output store — log entries, ring buffer, source filtering,
 * convenience helpers. Phase 6 (Output Panel) core functionality.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  useOutputStore,
  OUTPUT_SOURCES,
  logOutput,
  logToolOutput,
  logBuildOutput,
  logAgentOutput,
  logError,
  type OutputSource,
  type OutputLevel,
} from '../outputStore';

beforeEach(() => {
  useOutputStore.setState({
    entries: [],
    activeSource: null,
  });
});

describe('useOutputStore', () => {
  /* ─── Initial State ─────────────────────────────────────── */

  it('starts with no entries and null filter', () => {
    const state = useOutputStore.getState();
    expect(state.entries).toHaveLength(0);
    expect(state.activeSource).toBeNull();
    expect(state.maxEntries).toBeGreaterThan(0);
  });

  /* ─── addOutput ─────────────────────────────────────────-- */

  it('adds an output entry with generated id and timestamp', () => {
    useOutputStore.getState().addOutput({
      source: OUTPUT_SOURCES.SYSTEM,
      level: 'info',
      message: 'System started',
    });

    const entry = useOutputStore.getState().entries[0];
    expect(entry.message).toBe('System started');
    expect(entry.source).toBe(OUTPUT_SOURCES.SYSTEM);
    expect(entry.level).toBe('info');
    expect(entry.id).toMatch(/^out_/);
    expect(entry.timestamp).toBeDefined();
    expect(entry.data).toBeUndefined();
  });

  it('adds an entry with structured data', () => {
    useOutputStore.getState().addOutput({
      source: OUTPUT_SOURCES.TOOL,
      level: 'success',
      message: 'Build complete',
      data: { duration: 1200, files: 12 },
    });

    const entry = useOutputStore.getState().entries[0];
    expect(entry.data).toEqual({ duration: 1200, files: 12 });
  });

  it('maintains insertion order', () => {
    useOutputStore.getState().addOutput({ source: OUTPUT_SOURCES.SYSTEM, level: 'info', message: 'First' });
    useOutputStore.getState().addOutput({ source: OUTPUT_SOURCES.TOOL, level: 'info', message: 'Second' });
    useOutputStore.getState().addOutput({ source: OUTPUT_SOURCES.AGENT, level: 'info', message: 'Third' });

    const msgs = useOutputStore.getState().entries.map(e => e.message);
    expect(msgs).toEqual(['First', 'Second', 'Third']);
  });

  it('supports all output sources', () => {
    const sources: OutputSource[] = Object.values(OUTPUT_SOURCES);
    sources.forEach(src => {
      useOutputStore.getState().addOutput({ source: src, level: 'info', message: `Test ${src}` });
    });

    const entries = useOutputStore.getState().entries;
    expect(entries).toHaveLength(sources.length);
    sources.forEach(src => {
      expect(entries.some(e => e.source === src)).toBe(true);
    });
  });

  it('supports all output levels', () => {
    const levels: OutputLevel[] = ['info', 'success', 'warn', 'error', 'debug'];
    levels.forEach(lvl => {
      useOutputStore.getState().addOutput({ source: OUTPUT_SOURCES.SYSTEM, level: lvl, message: `Level ${lvl}` });
    });

    const entries = useOutputStore.getState().entries;
    expect(entries).toHaveLength(levels.length);
  });

  /* ─── clearOutput ───────────────────────────────────────── */

  it('clears all entries', () => {
    useOutputStore.getState().addOutput({ source: OUTPUT_SOURCES.SYSTEM, level: 'info', message: 'Log 1' });
    useOutputStore.getState().addOutput({ source: OUTPUT_SOURCES.TOOL, level: 'warn', message: 'Log 2' });

    useOutputStore.getState().clearOutput();

    expect(useOutputStore.getState().entries).toHaveLength(0);
  });

  /* ─── setActiveSource ─────────────────────────────────----- */

  it('sets the active source filter', () => {
    useOutputStore.getState().setActiveSource(OUTPUT_SOURCES.TOOL);
    expect(useOutputStore.getState().activeSource).toBe(OUTPUT_SOURCES.TOOL);
  });

  it('sets source filter to null (show all)', () => {
    useOutputStore.getState().setActiveSource(OUTPUT_SOURCES.TOOL);
    useOutputStore.getState().setActiveSource(null);
    expect(useOutputStore.getState().activeSource).toBeNull();
  });

  /* ─── Ring Buffer ───────────────────────────────────────── */

  it('trims old entries when exceeding maxEntries', () => {
    // Temporarily lower maxEntries for the test
    useOutputStore.setState({ maxEntries: 5 });

    for (let i = 0; i < 10; i++) {
      useOutputStore.getState().addOutput({
        source: OUTPUT_SOURCES.SYSTEM,
        level: 'info',
        message: `Log ${i}`,
      });
    }

    const entries = useOutputStore.getState().entries;
    expect(entries).toHaveLength(5);
    // Keeps the LAST 5 entries (ring buffer)
    expect(entries[0].message).toBe('Log 5');
    expect(entries[4].message).toBe('Log 9');
  });

  /* ─── Convenience Helpers ───────────────────────────────── */

  it('logOutput adds an entry via the store', () => {
    logOutput('Test log', OUTPUT_SOURCES.AGENT, 'warn', { key: 'val' });

    const entry = useOutputStore.getState().entries[0];
    expect(entry.message).toBe('Test log');
    expect(entry.source).toBe(OUTPUT_SOURCES.AGENT);
    expect(entry.level).toBe('warn');
    expect(entry.data).toEqual({ key: 'val' });
  });

  it('logOutput uses defaults for source and level', () => {
    logOutput('Default log');

    const entry = useOutputStore.getState().entries[0];
    expect(entry.source).toBe(OUTPUT_SOURCES.SYSTEM);
    expect(entry.level).toBe('info');
  });

  it('logToolOutput adds a tool entry', () => {
    logToolOutput('Tool executed', { tool: 'search' });

    const entry = useOutputStore.getState().entries[0];
    expect(entry.source).toBe(OUTPUT_SOURCES.TOOL);
    expect(entry.level).toBe('info');
    expect(entry.data).toEqual({ tool: 'search' });
  });

  it('logBuildOutput adds a build entry with custom level', () => {
    logBuildOutput('Build warning', 'warn');

    const entry = useOutputStore.getState().entries[0];
    expect(entry.source).toBe(OUTPUT_SOURCES.BUILD);
    expect(entry.level).toBe('warn');
  });

  it('logBuildOutput defaults to info level', () => {
    logBuildOutput('Build started');

    expect(useOutputStore.getState().entries[0].level).toBe('info');
  });

  it('logAgentOutput adds an agent entry', () => {
    logAgentOutput('Agent thinking', 'debug');

    const entry = useOutputStore.getState().entries[0];
    expect(entry.source).toBe(OUTPUT_SOURCES.AGENT);
    expect(entry.level).toBe('debug');
  });

  it('logError adds an error-level entry', () => {
    logError('Something broke', OUTPUT_SOURCES.BUILD);

    const entry = useOutputStore.getState().entries[0];
    expect(entry.source).toBe(OUTPUT_SOURCES.BUILD);
    expect(entry.level).toBe('error');
  });

  it('logError defaults source to System', () => {
    logError('Generic error');

    expect(useOutputStore.getState().entries[0].source).toBe(OUTPUT_SOURCES.SYSTEM);
  });

  it('all convenience helpers create separate entries', () => {
    logOutput('Output');
    logToolOutput('Tool');
    logBuildOutput('Build');
    logAgentOutput('Agent');
    logError('Error');

    expect(useOutputStore.getState().entries).toHaveLength(5);
  });
});
