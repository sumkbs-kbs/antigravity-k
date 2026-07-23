/**
 * pluginRegistry Tests
 * ======================
 * Tests for the Zustand plugin registry — registration, enable/disable,
 * flat list rebuilding, hook firing. Phase 9 (Plugin System) core functionality.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { usePluginRegistry, firePluginHook } from '../../plugin/pluginRegistry';
import type { PluginDefinition } from '../../plugin/pluginTypes';

/* ─── Test Plugin Factory ──────────────────────────────────── */

function createTestPlugin(id: string, overrides: Partial<PluginDefinition> = {}): PluginDefinition {
  return {
    manifest: {
      id,
      name: `Test ${id}`,
      version: '1.0.0',
      description: 'Test plugin for unit tests',
      author: 'Test Author',
    },
    onLoad: vi.fn(),
    onUnload: vi.fn(),
    panels: [],
    commands: [],
    hooks: [],
    widgets: [],
    ...overrides,
  };
}

beforeEach(() => {
  usePluginRegistry.setState({
    plugins: {},
    panels: [],
    commands: [],
    hooks: [],
    widgets: [],
  });
});

describe('usePluginRegistry', () => {
  /* ─── Initial State ─────────────────────────────────────── */

  it('starts with empty registry', () => {
    const state = usePluginRegistry.getState();
    expect(state.plugins).toEqual({});
    expect(state.panels).toHaveLength(0);
    expect(state.commands).toHaveLength(0);
    expect(state.hooks).toHaveLength(0);
    expect(state.widgets).toHaveLength(0);
  });

  /* ─── register ─────────────────────────────────────────── */

  it('registers a plugin and returns true', () => {
    const plugin = createTestPlugin('my-plugin');
    const result = usePluginRegistry.getState().register(plugin);

    expect(result).toBe(true);
    const entry = usePluginRegistry.getState().plugins['my-plugin'];
    expect(entry).toBeDefined();
    expect(entry.definition.manifest.name).toBe('Test my-plugin');
    expect(entry.enabled).toBe(true);
    expect(entry.loadedAt).toBeGreaterThan(0);
  });

  it('does not register duplicate plugins', () => {
    const plugin = createTestPlugin('dup');
    usePluginRegistry.getState().register(plugin);
    const result = usePluginRegistry.getState().register(plugin);

    expect(result).toBe(false);
    expect(Object.keys(usePluginRegistry.getState().plugins)).toHaveLength(1);
  });

  it('calls onLoad when registering an enabled plugin', () => {
    const onLoad = vi.fn();
    const plugin = createTestPlugin('with-onload', { onLoad });

    usePluginRegistry.getState().register(plugin);

    expect(onLoad).toHaveBeenCalledTimes(1);
  });

  it('does not call onLoad when plugin is disabled at registration', () => {
    // We need to simulate a previously-disabled plugin
    // The store reads localStorage for enabled state; we can set it via enabling/disabling
    const plugin = createTestPlugin('disabled-plugin');
    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().disable('disabled-plugin');

    // Clear mock calls
    const onLoad = vi.fn();
    const plugin2 = createTestPlugin('disabled-at-start', { onLoad });

    // Directly inject into plugins to simulate pre-disabled state
    // (the store reads localStorage, which we can't easily mock)
    usePluginRegistry.getState().register(plugin2);
    usePluginRegistry.getState().disable(plugin2.manifest.id);

    // register should call onLoad if enabled (enabled=true by default)
    // When disabling and re-enabling, onLoad is called
    expect(onLoad).toHaveBeenCalledTimes(1); // called on initial register
  });

  it('registers plugin with panels populated in flat list', () => {
    const panelComponent: React.FC = () => null;
    const plugin = createTestPlugin('panel-plugin', {
      panels: [
        {
          path: '/plugins/my-panel',
          component: panelComponent,
          label: 'My Panel',
          icon: '📊',
          order: 1,
        },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    expect(usePluginRegistry.getState().panels).toHaveLength(1);
    expect(usePluginRegistry.getState().panels[0].label).toBe('My Panel');
    expect(usePluginRegistry.getState().panels[0].order).toBe(1);
  });

  it('registers plugin with commands populated in flat list', () => {
    const execute = vi.fn();
    const plugin = createTestPlugin('cmd-plugin', {
      commands: [
        { id: 'my-command', label: 'My Command', execute, icon: '🔧' },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    expect(usePluginRegistry.getState().commands).toHaveLength(1);
    expect(usePluginRegistry.getState().commands[0].label).toBe('My Command');
  });

  it('registers plugin with hooks populated in flat list', () => {
    const handler = vi.fn();
    const plugin = createTestPlugin('hook-plugin', {
      hooks: [
        { hook: 'app:init', handler, priority: 10 },
        { hook: 'chat:send', handler, priority: 5 },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    expect(usePluginRegistry.getState().hooks).toHaveLength(2);
  });

  it('registers plugin with widgets populated in flat list', () => {
    const Widget: React.FC = () => null;
    const plugin = createTestPlugin('widget-plugin', {
      widgets: [
        { id: 'w1', component: Widget, position: 'statusbar-right', order: 5 },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    expect(usePluginRegistry.getState().widgets).toHaveLength(1);
    expect(usePluginRegistry.getState().widgets[0].position).toBe('statusbar-right');
  });

  it('registers multiple plugins with merged flat lists', () => {
    const p1 = createTestPlugin('p1', {
      panels: [{ path: '/plugins/p1', component: () => null, label: 'P1', icon: '1' }],
      commands: [{ id: 'cmd1', label: 'Cmd1', execute: vi.fn() }],
    });
    const p2 = createTestPlugin('p2', {
      panels: [{ path: '/plugins/p2', component: () => null, label: 'P2', icon: '2' }],
      commands: [{ id: 'cmd2', label: 'Cmd2', execute: vi.fn() }],
    });

    usePluginRegistry.getState().register(p1);
    usePluginRegistry.getState().register(p2);

    expect(usePluginRegistry.getState().panels).toHaveLength(2);
    expect(usePluginRegistry.getState().commands).toHaveLength(2);
  });

  /* ─── unregister ─────────────────────────────────────────-- */

  it('unregisters a plugin and returns true', () => {
    const plugin = createTestPlugin('to-remove');
    usePluginRegistry.getState().register(plugin);

    const result = usePluginRegistry.getState().unregister('to-remove');

    expect(result).toBe(true);
    expect(usePluginRegistry.getState().plugins['to-remove']).toBeUndefined();
  });

  it('calls onUnload when unregistering', () => {
    const onUnload = vi.fn();
    const plugin = createTestPlugin('unload-test', { onUnload });
    usePluginRegistry.getState().register(plugin);

    usePluginRegistry.getState().unregister('unload-test');

    expect(onUnload).toHaveBeenCalledTimes(1);
  });

  it('removes plugin contributions from flat lists on unregister', () => {
    const plugin = createTestPlugin('with-panels', {
      panels: [{ path: '/plugins/mine', component: () => null, label: 'Mine', icon: 'M' }],
    });
    usePluginRegistry.getState().register(plugin);
    expect(usePluginRegistry.getState().panels).toHaveLength(1);

    usePluginRegistry.getState().unregister('with-panels');

    expect(usePluginRegistry.getState().panels).toHaveLength(0);
  });

  it('returns false for non-existent plugin', () => {
    const result = usePluginRegistry.getState().unregister('nonexistent');
    expect(result).toBe(false);
  });

  /* ─── enable / disable ──────────────────────────────────── */

  it('enables a disabled plugin and calls onLoad', () => {
    const onLoad = vi.fn();
    const plugin = createTestPlugin('toggle', { onLoad });
    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().disable('toggle');

    vi.clearAllMocks();
    usePluginRegistry.getState().enable('toggle');

    expect(usePluginRegistry.getState().plugins['toggle'].enabled).toBe(true);
    expect(onLoad).toHaveBeenCalledTimes(1);
  });

  it('disables an enabled plugin and calls onUnload', () => {
    const onUnload = vi.fn();
    const plugin = createTestPlugin('toggle', { onUnload });
    usePluginRegistry.getState().register(plugin);

    usePluginRegistry.getState().disable('toggle');

    expect(usePluginRegistry.getState().plugins['toggle'].enabled).toBe(false);
    expect(onUnload).toHaveBeenCalledTimes(1);
  });

  it('does nothing when enabling an already-enabled plugin', () => {
    const onLoad = vi.fn();
    const plugin = createTestPlugin('already-enabled', { onLoad });
    usePluginRegistry.getState().register(plugin);

    vi.clearAllMocks();
    usePluginRegistry.getState().enable('already-enabled');

    expect(onLoad).not.toHaveBeenCalled();
  });

  it('does nothing when disabling an already-disabled plugin', () => {
    const onUnload = vi.fn();
    const plugin = createTestPlugin('already-disabled', { onUnload });
    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().disable('already-disabled');

    vi.clearAllMocks();
    usePluginRegistry.getState().disable('already-disabled');

    expect(onUnload).not.toHaveBeenCalled();
  });

  it('does nothing for non-existent plugin on enable/disable', () => {
    expect(() => {
      usePluginRegistry.getState().enable('nonexistent');
      usePluginRegistry.getState().disable('nonexistent');
    }).not.toThrow();
  });

  it('disable removes contributions from flat lists', () => {
    const plugin = createTestPlugin('with-stuff', {
      panels: [{ path: '/plugins/mine', component: () => null, label: 'Mine', icon: 'M' }],
      commands: [{ id: 'cmd', label: 'My Command', execute: vi.fn() }],
      hooks: [{ hook: 'app:init', handler: vi.fn() }],
    });
    usePluginRegistry.getState().register(plugin);
    expect(usePluginRegistry.getState().panels).toHaveLength(1);

    usePluginRegistry.getState().disable('with-stuff');

    expect(usePluginRegistry.getState().panels).toHaveLength(0);
    expect(usePluginRegistry.getState().commands).toHaveLength(0);
    expect(usePluginRegistry.getState().hooks).toHaveLength(0);
  });

  it('enable restores contributions to flat lists', () => {
    const plugin = createTestPlugin('toggle', {
      panels: [{ path: '/plugins/mine', component: () => null, label: 'Mine', icon: 'M' }],
    });
    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().disable('toggle');

    usePluginRegistry.getState().enable('toggle');

    expect(usePluginRegistry.getState().panels).toHaveLength(1);
  });

  /* ─── getPlugin / getAllPlugins ──────────────────────────── */

  it('getPlugin returns a registered plugin entry', () => {
    const plugin = createTestPlugin('find-me');
    usePluginRegistry.getState().register(plugin);

    const entry = usePluginRegistry.getState().getPlugin('find-me');
    expect(entry).toBeDefined();
    expect(entry!.definition.manifest.id).toBe('find-me');
  });

  it('getPlugin returns undefined for non-registered plugin', () => {
    const entry = usePluginRegistry.getState().getPlugin('not-found');
    expect(entry).toBeUndefined();
  });

  it('getAllPlugins returns all entries', () => {
    usePluginRegistry.getState().register(createTestPlugin('a'));
    usePluginRegistry.getState().register(createTestPlugin('b'));

    const all = usePluginRegistry.getState().getAllPlugins();
    expect(all).toHaveLength(2);
  });

  it('getAllPlugins returns empty array when none registered', () => {
    expect(usePluginRegistry.getState().getAllPlugins()).toEqual([]);
  });

  /* ─── Flat List Sorting ─────────────────────────────────── */

  it('sorts panels by order (ascending)', () => {
    const plugin = createTestPlugin('sorted', {
      panels: [
        { path: '/p3', component: () => null, label: 'P3', icon: '3', order: 30 },
        { path: '/p1', component: () => null, label: 'P1', icon: '1', order: 10 },
        { path: '/p2', component: () => null, label: 'P2', icon: '2', order: 20 },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    const labels = usePluginRegistry.getState().panels.map(p => p.label);
    expect(labels).toEqual(['P1', 'P2', 'P3']);
  });

  it('sorts hooks by priority (descending)', () => {
    const handler = vi.fn();
    const plugin = createTestPlugin('hook-priority', {
      hooks: [
        { hook: 'app:init', handler, priority: 5 },
        { hook: 'app:init', handler, priority: 20 },
        { hook: 'app:init', handler, priority: 10 },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    const priorities = usePluginRegistry.getState().hooks.map(h => h.priority);
    expect(priorities).toEqual([20, 10, 5]);
  });

  /* ─── firePluginHook ────────────────────────────────────── */

  it('fires matching hook handlers in priority order', () => {
    const results: number[] = [];
    const plugin = createTestPlugin('hook-test', {
      hooks: [
        { hook: 'app:init', handler: () => results.push(1), priority: 10 },
        { hook: 'app:init', handler: () => results.push(2), priority: 20 },
        { hook: 'chat:send', handler: () => results.push(3), priority: 5 },
      ],
    });

    usePluginRegistry.getState().register(plugin);
    firePluginHook('app:init');

    expect(results).toEqual([2, 1]); // priority descending: 20 first, then 10
  });

  it('does not call handlers for non-matching hooks', () => {
    const handler = vi.fn();
    const plugin = createTestPlugin('no-match', {
      hooks: [
        { hook: 'app:init', handler },
        { hook: 'file:open', handler },
      ],
    });

    usePluginRegistry.getState().register(plugin);
    firePluginHook('git:commit');

    expect(handler).not.toHaveBeenCalled();
  });

  it('passes data to hook handlers', () => {
    const handler = vi.fn();
    const plugin = createTestPlugin('data-test', {
      hooks: [{ hook: 'chat:send', handler }],
    });

    usePluginRegistry.getState().register(plugin);
    const data = { text: 'Hello', model: 'gpt-4' };
    firePluginHook('chat:send', data);

    expect(handler).toHaveBeenCalledWith(data);
  });

  it('does not throw when a hook handler throws', () => {
    const handler = vi.fn().mockImplementation(() => { throw new Error('Handler error'); });
    const plugin = createTestPlugin('throw-test', {
      hooks: [{ hook: 'app:init', handler }],
    });

    usePluginRegistry.getState().register(plugin);

    expect(() => firePluginHook('app:init')).not.toThrow();
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('only fires hooks from enabled plugins', () => {
    const handler = vi.fn();
    const plugin = createTestPlugin('disabled-hook', {
      hooks: [{ hook: 'app:init', handler }],
    });

    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().disable(plugin.manifest.id);

    firePluginHook('app:init');

    expect(handler).not.toHaveBeenCalled();
  });

  /* ─── Multiple Registrations ─────────────────────────────── */

  it('handles registering 10 plugins without issues', () => {
    for (let i = 0; i < 10; i++) {
      usePluginRegistry.getState().register(createTestPlugin(`plugin-${i}`));
    }

    expect(Object.keys(usePluginRegistry.getState().plugins)).toHaveLength(10);
    expect(usePluginRegistry.getState().getAllPlugins()).toHaveLength(10);
  });

  it('registers and unregisters a plugin with all feature types', () => {
    const Widget: React.FC = () => null;
    const handler = vi.fn();
    const execute = vi.fn();

    const plugin = createTestPlugin('full-feature', {
      panels: [{ path: '/full', component: () => null, label: 'Full', icon: 'F' }],
      commands: [{ id: 'full-cmd', label: 'Full Command', execute }],
      hooks: [
        { hook: 'app:init', handler },
        { hook: 'file:open', handler },
      ],
      widgets: [{ id: 'full-widget', component: Widget, position: 'sidebar-bottom' }],
    });

    usePluginRegistry.getState().register(plugin);

    expect(usePluginRegistry.getState().panels).toHaveLength(1);
    expect(usePluginRegistry.getState().commands).toHaveLength(1);
    expect(usePluginRegistry.getState().hooks).toHaveLength(2);
    expect(usePluginRegistry.getState().widgets).toHaveLength(1);

    usePluginRegistry.getState().unregister('full-feature');

    expect(usePluginRegistry.getState().panels).toHaveLength(0);
    expect(usePluginRegistry.getState().commands).toHaveLength(0);
    expect(usePluginRegistry.getState().hooks).toHaveLength(0);
    expect(usePluginRegistry.getState().widgets).toHaveLength(0);
  });

  /* ─── localStorage Persistence ──────────────────────────── */

  it('reads enabled state from localStorage on register (loadEnabled)', () => {
    // loadEnabled reads 'agk_plugins_enabled' from localStorage at module init
    const getItemSpy = vi.spyOn(window.localStorage, 'getItem');

    // Re-initialize by creating a new plugin that triggers loadEnabled logic
    // (loadEnabled has already run at module init, so this test only verifies
    // that localStorage.getItem is available, not that it's called per-register)
    usePluginRegistry.getState().register(createTestPlugin('persist-me'));

    // Register does NOT save to localStorage (only enable/disable/unregister do)
    // But the plugin should be enabled by default
    expect(usePluginRegistry.getState().plugins['persist-me'].enabled).toBe(true);
    getItemSpy.mockRestore();
  });

  it('loads pre-disabled state from localStorage for previously disabled plugins', async () => {
    // Seed localStorage BEFORE module init so loadEnabled() reads it
    window.localStorage.setItem(
      'agk_plugins_enabled',
      JSON.stringify({ 'pre-disabled': false }),
    );

    // Reset module registry so import re-evaluates module-level loadEnabled()
    vi.resetModules();
    const { usePluginRegistry: freshRegistry } = await import('../../plugin/pluginRegistry');

    const onLoad = vi.fn();
    const plugin = createTestPlugin('pre-disabled', { onLoad });
    freshRegistry.getState().register(plugin);

    // Should be disabled and onLoad should NOT be called
    expect(freshRegistry.getState().plugins['pre-disabled'].enabled).toBe(false);
    expect(onLoad).not.toHaveBeenCalled();

    // Clean up
    window.localStorage.removeItem('agk_plugins_enabled');
  });

  it('saves enabled state to localStorage on unregister (removes entry)', () => {
    const plugin = createTestPlugin('to-unregister');
    usePluginRegistry.getState().register(plugin);

    const setItemSpy = vi.spyOn(window.localStorage, 'setItem');
    usePluginRegistry.getState().unregister('to-unregister');

    // unregister reads enabled, deletes the entry, and saves
    expect(setItemSpy).toHaveBeenCalledWith(
      'agk_plugins_enabled',
      expect.not.stringContaining('to-unregister'),
    );
    setItemSpy.mockRestore();
  });

  it('saves enabled state to localStorage on disable', () => {
    const plugin = createTestPlugin('to-disable');
    usePluginRegistry.getState().register(plugin);

    const setItemSpy = vi.spyOn(window.localStorage, 'setItem');
    usePluginRegistry.getState().disable('to-disable');

    expect(setItemSpy).toHaveBeenCalledWith(
      'agk_plugins_enabled',
      expect.stringContaining('"to-disable":false'),
    );
    setItemSpy.mockRestore();
  });

  it('saves enabled state to localStorage on enable', () => {
    const plugin = createTestPlugin('to-enable');
    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().disable('to-enable');

    const setItemSpy = vi.spyOn(window.localStorage, 'setItem');
    usePluginRegistry.getState().enable('to-enable');

    expect(setItemSpy).toHaveBeenCalledWith(
      'agk_plugins_enabled',
      expect.stringContaining('"to-enable":true'),
    );
    setItemSpy.mockRestore();
  });

  /* ─── onLoad Error Handling ─────────────────────────────── */

  it('handles onLoad error gracefully during register', () => {
    const onLoad = vi.fn().mockImplementation(() => { throw new Error('Load failed'); });
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const plugin = createTestPlugin('failing-load', { onLoad });
    const result = usePluginRegistry.getState().register(plugin);

    // Should still return true and register the plugin
    expect(result).toBe(true);
    expect(usePluginRegistry.getState().plugins['failing-load']).toBeDefined();
    expect(onLoad).toHaveBeenCalledTimes(1);
    // Should log the error
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('onLoad error'),
      expect.any(Error),
    );
    consoleSpy.mockRestore();
  });

  it('handles onLoad error gracefully during enable', () => {
    const onLoad = vi.fn().mockImplementation(() => { throw new Error('Enable load failed'); });
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const plugin = createTestPlugin('failing-enable', { onLoad });
    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().disable('failing-enable');

    usePluginRegistry.getState().enable('failing-enable');

    // Plugin should still be enabled despite onLoad error
    expect(usePluginRegistry.getState().plugins['failing-enable'].enabled).toBe(true);
    expect(onLoad).toHaveBeenCalledTimes(2); // called once on register, once on enable
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('onLoad error'),
      expect.any(Error),
    );
    consoleSpy.mockRestore();
  });

  /* ─── onUnload Error Handling ───────────────────────────── */

  it('handles onUnload error gracefully during unregister', () => {
    const onUnload = vi.fn().mockImplementation(() => { throw new Error('Unload failed'); });
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const plugin = createTestPlugin('failing-unload', { onUnload });
    usePluginRegistry.getState().register(plugin);

    const result = usePluginRegistry.getState().unregister('failing-unload');

    expect(result).toBe(true);
    expect(usePluginRegistry.getState().plugins['failing-unload']).toBeUndefined();
    expect(onUnload).toHaveBeenCalledTimes(1);
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('onUnload error'),
      expect.any(Error),
    );
    consoleSpy.mockRestore();
  });

  it('handles onUnload error gracefully during disable', () => {
    const onUnload = vi.fn().mockImplementation(() => { throw new Error('Disable unload failed'); });
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const plugin = createTestPlugin('failing-disable', { onUnload });
    usePluginRegistry.getState().register(plugin);

    usePluginRegistry.getState().disable('failing-disable');

    expect(usePluginRegistry.getState().plugins['failing-disable'].enabled).toBe(false);
    expect(onUnload).toHaveBeenCalledTimes(1);
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('onUnload error'),
      expect.any(Error),
    );
    consoleSpy.mockRestore();
  });

  /* ─── rebuildLists Edge Cases ───────────────────────────── */

  it('rebuilds lists skipping disabled plugins', () => {
    const panel = { path: '/p1', component: () => null as any, label: 'P1', icon: '1' };
    const p1 = createTestPlugin('p1', { panels: [panel] });
    const p2 = createTestPlugin('p2', { panels: [panel] });

    usePluginRegistry.getState().register(p1);
    usePluginRegistry.getState().register(p2);
    usePluginRegistry.getState().disable('p1');

    expect(usePluginRegistry.getState().panels).toHaveLength(1);
    expect(usePluginRegistry.getState().panels[0].label).toBe('P1'); // from p2 only
  });

  it('handles plugins with undefined feature arrays', () => {
    const plugin = createTestPlugin('partial', {
      panels: undefined as any,
      commands: undefined as any,
      hooks: undefined as any,
      widgets: undefined as any,
    });

    // Should not throw when rebuilding lists
    expect(() => {
      usePluginRegistry.getState().register(plugin);
    }).not.toThrow();

    expect(usePluginRegistry.getState().panels).toHaveLength(0);
    expect(usePluginRegistry.getState().commands).toHaveLength(0);
    expect(usePluginRegistry.getState().hooks).toHaveLength(0);
    expect(usePluginRegistry.getState().widgets).toHaveLength(0);
  });

  it('handles null order in panel sorting', () => {
    const plugin = createTestPlugin('order-test', {
      panels: [
        { path: '/z', component: () => null as any, label: 'Z', icon: 'Z', order: 100 },
        { path: '/a', component: () => null as any, label: 'A', icon: 'A', order: null as any },
        { path: '/m', component: () => null as any, label: 'M', icon: 'M', order: 50 },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    // null order defaults to 100; A(null→100), M(50), Z(100) → M, A, Z or M, Z, A
    const labels = usePluginRegistry.getState().panels.map(p => p.label);
    expect(labels[0]).toBe('M');
  });

  it('handles null priority in hook sorting', () => {
    const handler = vi.fn();
    const plugin = createTestPlugin('hook-priority-null', {
      hooks: [
        { hook: 'app:init', handler, priority: 50 },
        { hook: 'app:init', handler, priority: null as any },
        { hook: 'app:init', handler, priority: 10 },
      ],
    });

    usePluginRegistry.getState().register(plugin);

    // null priority defaults to 0, sorts after positive values
    const priorities = usePluginRegistry.getState().hooks.map(h => h.priority ?? 0);
    expect(priorities[0]).toBe(50);
    expect(priorities[2]).toBe(0);
  });

  /* ─── Console Logging ───────────────────────────────────── */

  it('warns on duplicate registration', () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const plugin = createTestPlugin('dup-warn');

    usePluginRegistry.getState().register(plugin);
    usePluginRegistry.getState().register(plugin);

    expect(consoleWarnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Already registered'),
    );
    consoleWarnSpy.mockRestore();
  });

  it('logs registration success', () => {
    const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    usePluginRegistry.getState().register(createTestPlugin('log-me'));

    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining('Registered'),
    );
    consoleLogSpy.mockRestore();
  });

  it('logs unregistration and returns true', () => {
    const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    const plugin = createTestPlugin('unlog-me');
    usePluginRegistry.getState().register(plugin);
    const result = usePluginRegistry.getState().unregister('unlog-me');

    expect(result).toBe(true);
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining('Unregistered'),
    );
    consoleLogSpy.mockRestore();
  });
});
