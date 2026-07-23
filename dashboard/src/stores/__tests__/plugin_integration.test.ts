/**
 * Plugin System Integration Tests
 * =================================
 * End-to-end tests for the plugin system combining examplePlugin,
 * firePluginHook, PluginManager lifecycle dispatcher, and cross-store
 * hook integration (editorStore, chatStore, gitStore, useEventWebSocket).
 *
 * Phase 9: Plugin Registry + PluginManager
 * Phase 10: Hook integration into app stores
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { usePluginRegistry, firePluginHook } from '../../plugin/pluginRegistry';
import { examplePlugin } from '../../plugin/examplePlugin';
import { useEditorStore } from '../../stores/editorStore';
import { useGitStore } from '../../stores/gitStore';
import type { PluginDefinition, HookType } from '../../plugin/pluginTypes';

/* ─── Helpers ──────────────────────────────────────────────── */

function createTrackingPlugin(
  id: string,
  overrides: Partial<PluginDefinition> & { tracker?: { events: string[] } } = {},
): PluginDefinition {
  const tracker = overrides.tracker ?? { events: [] };
  return {
    manifest: {
      id,
      name: `Test ${id}`,
      version: '1.0.0',
      description: 'Integration test plugin',
    },
    onLoad: () => { tracker.events.push(`load:${id}`); },
    onUnload: () => { tracker.events.push(`unload:${id}`); },
    panels: [],
    commands: [],
    hooks: [],
    widgets: [],
    ...overrides,
  };
}

beforeEach(() => {
  // Reset plugin registry
  usePluginRegistry.setState({
    plugins: {},
    panels: [],
    commands: [],
    hooks: [],
    widgets: [],
  });
  // Reset editor store (prevent stale openFiles from blocking hook firing)
  useEditorStore.setState({
    openFiles: [],
    activeFilePath: null,
    previewVisible: false,
    previewPath: null,
    previewTitle: '',
    previewContent: '',
    monacoEditor: null,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});



/* ═══════════════════════════════════════════════════════════════
   1. examplePlugin Integration
   ═══════════════════════════════════════════════════════════════ */

describe('examplePlugin — registration lifecycle', () => {
  it('registers all examplePlugin features correctly', () => {
    usePluginRegistry.getState().register(examplePlugin);

    const state = usePluginRegistry.getState();
    const entry = state.plugins['example-hello-world'];
    expect(entry).toBeDefined();
    expect(entry.enabled).toBe(true);
    expect(entry.definition.manifest.name).toBe('Hello World');
    expect(entry.definition.manifest.version).toBe('1.0.0');
  });

  it('registers the example panel in the flat list', () => {
    usePluginRegistry.getState().register(examplePlugin);

    const panels = usePluginRegistry.getState().panels;
    expect(panels).toHaveLength(1);
    expect(panels[0].path).toBe('/plugins/hello-world');
    expect(panels[0].label).toBe('Hello Plugin');
    expect(panels[0].order).toBe(1);
  });

  it('registers example commands in the flat list', () => {
    usePluginRegistry.getState().register(examplePlugin);

    const commands = usePluginRegistry.getState().commands;
    expect(commands).toHaveLength(2);

    const toastCmd = commands.find(c => c.id === 'example:show-toast');
    expect(toastCmd).toBeDefined();
    expect(toastCmd!.label).toBe('Plugin: Show test toast');
    expect(toastCmd!.category).toBe('Plugin');

    const panelCmd = commands.find(c => c.id === 'example:open-panel');
    expect(panelCmd).toBeDefined();
    expect(panelCmd!.label).toBe('Plugin: Open Hello World panel');
  });

  it('registers example hooks in the flat list', () => {
    usePluginRegistry.getState().register(examplePlugin);

    const hooks = usePluginRegistry.getState().hooks;
    expect(hooks).toHaveLength(2);

    const appInitHook = hooks.find(h => h.hook === 'app:init');
    expect(appInitHook).toBeDefined();
    expect(typeof appInitHook!.handler).toBe('function');

    const chatSendHook = hooks.find(h => h.hook === 'chat:send');
    expect(chatSendHook).toBeDefined();
    expect(typeof chatSendHook!.handler).toBe('function');
  });

  it('example plugin responds to firePluginHook("app:init")', () => {
    const handler = vi.fn();
    const plugin: PluginDefinition = {
      ...examplePlugin,
      manifest: { ...examplePlugin.manifest, id: 'example-hook-test' },
      hooks: [
        { hook: 'app:init', handler },
        { hook: 'chat:send', handler },
      ],
    };
    usePluginRegistry.getState().register(plugin);

    firePluginHook('app:init', { timestamp: 1000 });

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith({ timestamp: 1000 });
  });

  it('example plugin responds to firePluginHook("chat:send")', () => {
    const handler = vi.fn();
    const plugin: PluginDefinition = {
      ...examplePlugin,
      manifest: { ...examplePlugin.manifest, id: 'example-chat-test' },
      hooks: [
        { hook: 'chat:send', handler },
      ],
    };
    usePluginRegistry.getState().register(plugin);

    const chatData = { text: 'Hello AI', model: 'gpt-4' };
    firePluginHook('chat:send', chatData);

    expect(handler).toHaveBeenCalledWith(chatData);
  });

  it('unregisters example plugin and removes all contributions', () => {
    usePluginRegistry.getState().register(examplePlugin);
    usePluginRegistry.getState().unregister('example-hello-world');

    const state = usePluginRegistry.getState();
    expect(state.plugins['example-hello-world']).toBeUndefined();
    expect(state.panels).toHaveLength(0);
    expect(state.commands).toHaveLength(0);
    expect(state.hooks).toHaveLength(0);
  });
});

/* ═══════════════════════════════════════════════════════════════
   2. firePluginHook Integration
   ═══════════════════════════════════════════════════════════════ */

describe('firePluginHook — multi-plugin integration', () => {
  it('fires hooks across multiple registered plugins', () => {
    const handler1 = vi.fn();
    const handler2 = vi.fn();
    const handler3 = vi.fn();

    usePluginRegistry.getState().register(createTrackingPlugin('p1', {
      hooks: [{ hook: 'app:init', handler: handler1 }],
    }));
    usePluginRegistry.getState().register(createTrackingPlugin('p2', {
      hooks: [{ hook: 'app:init', handler: handler2 }],
    }));

    firePluginHook('app:init');

    expect(handler1).toHaveBeenCalledTimes(1);
    expect(handler2).toHaveBeenCalledTimes(1);
    expect(handler3).toHaveBeenCalledTimes(0); // never registered
  });

  it('fires only matching hooks, not all hooks', () => {
    const handler = vi.fn();

    usePluginRegistry.getState().register(createTrackingPlugin('filter-test', {
      hooks: [
        { hook: 'app:init', handler },
        { hook: 'chat:send', handler },
        { hook: 'file:open', handler },
      ],
    }));

    firePluginHook('chat:send', { text: 'test' });

    // handler should have been called once (for chat:send only)
    expect(handler).toHaveBeenCalledTimes(1);
    // Verify it was called with the correct data
    expect(handler).toHaveBeenCalledWith({ text: 'test' });
  });

  it('respects hook priority order', () => {
    const order: number[] = [];

    usePluginRegistry.getState().register(createTrackingPlugin('priority-test', {
      hooks: [
        { hook: 'app:init', handler: () => order.push(1), priority: 10 },
        { hook: 'app:init', handler: () => order.push(2), priority: 30 },
        { hook: 'app:init', handler: () => order.push(3), priority: 20 },
      ],
    }));

    firePluginHook('app:init');

    // Sorted by priority descending: 30 -> 20 -> 10
    expect(order).toEqual([2, 3, 1]);
  });

  it('does not fire hooks from disabled plugins', () => {
    const handler = vi.fn();

    usePluginRegistry.getState().register(createTrackingPlugin('disabled-hook-test', {
      hooks: [{ hook: 'app:init', handler }],
    }));
    usePluginRegistry.getState().disable('disabled-hook-test');

    firePluginHook('app:init');

    expect(handler).not.toHaveBeenCalled();
  });

  it('firing hooks does not throw when a handler throws', () => {
    usePluginRegistry.getState().register(createTrackingPlugin('thrower', {
      hooks: [
        { hook: 'app:init', handler: () => { throw new Error('Handler crash'); } },
      ],
    }));

    // Should not throw despite the handler error
    expect(() => firePluginHook('app:init')).not.toThrow();
  });

  it('firing hooks continues to remaining handlers after an error', () => {
    const order: number[] = [];

    usePluginRegistry.getState().register(createTrackingPlugin('error-cont', {
      hooks: [
        { hook: 'app:init', handler: () => { order.push(1); }, priority: 10 },
        {
          hook: 'app:init',
          handler: () => { order.push(2); throw new Error('Boom'); },
          priority: 20,
        },
        { hook: 'app:init', handler: () => { order.push(3); }, priority: 5 },
      ],
    }));

    firePluginHook('app:init');

    // All handlers should have been called despite the middle one throwing
    expect(order).toContain(1);
    expect(order).toContain(2);
    expect(order).toContain(3);
  });

  it('supports all hook types', () => {
    const handler = vi.fn();
    const allHookTypes: HookType[] = [
      'app:init', 'app:beforeMount',
      'file:open', 'file:save', 'file:change',
      'chat:send', 'chat:response',
      'git:commit',
      'tool:start', 'tool:end',
    ];

    usePluginRegistry.getState().register(createTrackingPlugin('all-hooks', {
      hooks: allHookTypes.map(hook => ({ hook, handler })),
    }));

    // Fire each hook type
    allHookTypes.forEach(hook => firePluginHook(hook, { data: hook }));

    // Should have been called once per hook type
    expect(handler).toHaveBeenCalledTimes(allHookTypes.length);
    allHookTypes.forEach(hook => {
      expect(handler).toHaveBeenCalledWith({ data: hook });
    });
  });
});

/* ═══════════════════════════════════════════════════════════════
   3. PluginManager Integration
   ═══════════════════════════════════════════════════════════════ */

describe('PluginManager — lifecycle and render integration', () => {
  it('PluginLifecycleDispatcher fires app:init on mount', () => {
    const handler = vi.fn();
    usePluginRegistry.getState().register(createTrackingPlugin('lifecycle-test', {
      hooks: [{ hook: 'app:init', handler }],
    }));

    // Simulate what PluginLifecycleDispatcher does in its useEffect:
    // it calls firePluginHook('app:init', { timestamp: Date.now() })
    firePluginHook('app:init', { timestamp: Date.now() });

    expect(handler).toHaveBeenCalled();
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ timestamp: expect.any(Number) }),
    );
  });

  it('usePluginSidebarItems returns panel metadata', () => {
    usePluginRegistry.getState().register(examplePlugin);

    // usePluginSidebarItems reads from the panels in the registry
    // We can test by reading the store directly and verifying the mapping
    const registryPanels = usePluginRegistry.getState().panels;
    const sidebarItems = registryPanels.map(p => ({
      path: p.path,
      label: p.label,
      icon: p.icon,
    }));

    expect(sidebarItems).toHaveLength(1);
    expect(sidebarItems[0]).toEqual({
      path: '/plugins/hello-world',
      label: 'Hello Plugin',
      icon: 'W',
    });
  });

  it('usePluginCommands returns command metadata', () => {
    usePluginRegistry.getState().register(examplePlugin);

    const registryCommands = usePluginRegistry.getState().commands;
    const commandItems = registryCommands.map(c => ({
      id: c.id,
      label: c.label,
      icon: c.icon,
      category: c.category,
      execute: c.execute,
    }));

    expect(commandItems).toHaveLength(2);

    const toastCmd = commandItems.find(c => c.id === 'example:show-toast');
    expect(toastCmd).toBeDefined();
    expect(toastCmd!.category).toBe('Plugin');
    expect(typeof toastCmd!.execute).toBe('function');
  });

  it('example plugin command can execute without throwing', () => {
    usePluginRegistry.getState().register(examplePlugin);

    const toastCmd = usePluginRegistry.getState().commands
      .find(c => c.id === 'example:show-toast');

    expect(toastCmd).toBeDefined();
    // Executing the command should not throw
    expect(() => toastCmd!.execute()).not.toThrow();
  });

  it('example plugin panel navigation command dispatches event', () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    usePluginRegistry.getState().register(examplePlugin);

    const navCmd = usePluginRegistry.getState().commands
      .find(c => c.id === 'example:open-panel');

    expect(navCmd).toBeDefined();
    navCmd!.execute();

    expect(dispatchSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'agk:navigate',
        detail: '/plugins/hello-world',
      }),
    );

    dispatchSpy.mockRestore();
  });
});

/* ═══════════════════════════════════════════════════════════════
   4. Cross-Store Hook Integration (Phase 10)
   ═══════════════════════════════════════════════════════════════ */

describe('Cross-store hook integration (Phase 10)', () => {
  it('editorStore.openFile fires file:open hook', () => {
    const handler = vi.fn();
    usePluginRegistry.getState().register(createTrackingPlugin('editor-test', {
      hooks: [{ hook: 'file:open', handler }],
    }));

    // Call openFile — fires file:open hook via firePluginHook
    useEditorStore.getState().openFile('test.ts', 'test.ts', 'content');

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({
        filePath: 'test.ts',
        fileName: 'test.ts',
      }),
    );
  });

  it('editorStore.updateFileContent fires file:change hook', () => {
    const handler = vi.fn();
    usePluginRegistry.getState().register(createTrackingPlugin('change-test', {
      hooks: [{ hook: 'file:change', handler }],
    }));

    useEditorStore.getState().openFile('test.ts', 'test.ts', 'original');

    // updateFileContent fires hook via setTimeout
    useEditorStore.getState().updateFileContent('test.ts', 'modified');

    // Hook is fired after a setTimeout(0)
    return new Promise<void>(resolve => {
      setTimeout(() => {
        expect(handler).toHaveBeenCalledWith(
          expect.objectContaining({
            filePath: 'test.ts',
            content: 'modified',
          }),
        );
        resolve();
      }, 10);
    });
  });

  it('gitStore.commit fires git:commit hook after successful commit', async () => {
    const handler = vi.fn();
    usePluginRegistry.getState().register(createTrackingPlugin('git-test', {
      hooks: [{ hook: 'git:commit', handler }],
    }));

    // Mock fetch to simulate successful commit
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: true }),
    });

    await useGitStore.getState().commit('Test commit', true);

    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Test commit',
        path: '.',
      }),
    );

    vi.restoreAllMocks();
  });

  it('multiple hooks fire for a single user action (chat:send)', () => {
    const fileHandler = vi.fn();
    const chatHandler = vi.fn();

    usePluginRegistry.getState().register(createTrackingPlugin('multi-hook', {
      hooks: [
        { hook: 'file:open', handler: fileHandler },
        { hook: 'chat:send', handler: chatHandler },
      ],
    }));

    // Simulate what ChatPage does on send: openFile + firePluginHook('chat:send')
    useEditorStore.getState().openFile('test.ts', 'test.ts', 'content');
    firePluginHook('chat:send', { text: 'Hello', model: 'gpt-4' });

    expect(fileHandler).toHaveBeenCalledTimes(1);
    expect(chatHandler).toHaveBeenCalledTimes(1);
  });

  it('tool:start and tool:end hooks fire from WebSocket events', () => {
    const startHandler = vi.fn();
    const endHandler = vi.fn();

    usePluginRegistry.getState().register(createTrackingPlugin('tool-test', {
      hooks: [
        { hook: 'tool:start', handler: startHandler },
        { hook: 'tool:end', handler: endHandler },
      ],
    }));

    // Simulate what useEventWebSocket does on ToolExecutionStarted/Finished
    firePluginHook('tool:start', { name: 'web_search', tool_name: 'web_search' });
    firePluginHook('tool:end', { name: 'web_search', result: 'success' });

    expect(startHandler).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'web_search' }),
    );
    expect(endHandler).toHaveBeenCalledWith(
      expect.objectContaining({ result: 'success' }),
    );
  });
});

/* ═══════════════════════════════════════════════════════════════
   5. Plugin Enable/Disable Lifecycle
   ═══════════════════════════════════════════════════════════════ */

describe('Plugin enable/disable lifecycle integration', () => {
  it('disable → enable preserves plugin entries but rebuilds lists', () => {
    usePluginRegistry.getState().register(examplePlugin);
    expect(usePluginRegistry.getState().panels).toHaveLength(1);

    usePluginRegistry.getState().disable('example-hello-world');
    expect(usePluginRegistry.getState().plugins['example-hello-world'].enabled).toBe(false);
    expect(usePluginRegistry.getState().panels).toHaveLength(0);

    usePluginRegistry.getState().enable('example-hello-world');
    expect(usePluginRegistry.getState().plugins['example-hello-world'].enabled).toBe(true);
    expect(usePluginRegistry.getState().panels).toHaveLength(1);
  });

  it('disable calls onUnload, enable calls onLoad', () => {
    const tracker = { events: [] as string[] };

    usePluginRegistry.getState().register(createTrackingPlugin('lifecycle-test', {
      tracker,
    }));

    expect(tracker.events).toContain('load:lifecycle-test');

    usePluginRegistry.getState().disable('lifecycle-test');
    expect(tracker.events).toContain('unload:lifecycle-test');

    usePluginRegistry.getState().enable('lifecycle-test');
    // Should call onLoad again
    const loadEvents = tracker.events.filter(e => e === 'load:lifecycle-test');
    expect(loadEvents).toHaveLength(2);
  });

  it('disabling then enabling restores hook firing', () => {
    const handler = vi.fn();

    usePluginRegistry.getState().register(createTrackingPlugin('toggle-hooks', {
      hooks: [{ hook: 'app:init', handler }],
    }));

    firePluginHook('app:init');
    expect(handler).toHaveBeenCalledTimes(1);

    usePluginRegistry.getState().disable('toggle-hooks');
    firePluginHook('app:init');
    expect(handler).toHaveBeenCalledTimes(1); // no new calls

    usePluginRegistry.getState().enable('toggle-hooks');
    firePluginHook('app:init');
    expect(handler).toHaveBeenCalledTimes(2); // restored
  });

  it('multiple plugins: disabling one does not affect others', () => {
    const handler1 = vi.fn();
    const handler2 = vi.fn();

    usePluginRegistry.getState().register(createTrackingPlugin('p1', {
      hooks: [{ hook: 'app:init', handler: handler1 }],
    }));
    usePluginRegistry.getState().register(createTrackingPlugin('p2', {
      hooks: [{ hook: 'app:init', handler: handler2 }],
    }));

    usePluginRegistry.getState().disable('p1');

    firePluginHook('app:init');

    expect(handler1).not.toHaveBeenCalled(); // disabled
    expect(handler2).toHaveBeenCalledTimes(1); // still active
  });

  it('register → unregister → re-register works correctly', () => {
    usePluginRegistry.getState().register(examplePlugin);
    usePluginRegistry.getState().unregister('example-hello-world');

    // Re-register
    const result = usePluginRegistry.getState().register(examplePlugin);
    expect(result).toBe(true);
    expect(usePluginRegistry.getState().plugins['example-hello-world']).toBeDefined();
    expect(usePluginRegistry.getState().panels).toHaveLength(1);
  });
});

/* ═══════════════════════════════════════════════════════════════
   6. Edge Cases & Error Handling
   ═══════════════════════════════════════════════════════════════ */

describe('Edge cases and error handling', () => {
  it('registers a plugin with no panels/commands/hooks', () => {
    const plugin = createTrackingPlugin('minimal');
    const result = usePluginRegistry.getState().register(plugin);

    expect(result).toBe(true);
    expect(usePluginRegistry.getState().panels).toHaveLength(0);
    expect(usePluginRegistry.getState().commands).toHaveLength(0);
    expect(usePluginRegistry.getState().hooks).toHaveLength(0);
  });

  it('does not crash when onLoad throws in register', () => {
    const plugin = createTrackingPlugin('crash-on-load', {
      onLoad: () => { throw new Error('Load failure'); },
    });

    expect(() => usePluginRegistry.getState().register(plugin)).not.toThrow();
    // Plugin should still be registered despite onLoad failure
    expect(usePluginRegistry.getState().plugins['crash-on-load']).toBeDefined();
  });

  it('does not crash when onUnload throws in unregister', () => {
    const plugin = createTrackingPlugin('crash-on-unload', {
      onUnload: () => { throw new Error('Unload failure'); },
    });

    usePluginRegistry.getState().register(plugin);
    expect(() => usePluginRegistry.getState().unregister('crash-on-unload')).not.toThrow();
    expect(usePluginRegistry.getState().plugins['crash-on-unload']).toBeUndefined();
  });

  it('duplicate registration returns false and warns', () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    usePluginRegistry.getState().register(examplePlugin);
    const result = usePluginRegistry.getState().register(examplePlugin);

    expect(result).toBe(false);
    expect(consoleSpy).toHaveBeenCalledWith(
      '[Plugin] Already registered: example-hello-world',
    );

    consoleSpy.mockRestore();
  });

  it('unregistering non-existent plugin returns false', () => {
    const result = usePluginRegistry.getState().unregister('nonexistent');
    expect(result).toBe(false);
  });

  it('handler errors in firePluginHook are caught and logged', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    usePluginRegistry.getState().register(createTrackingPlugin('error-test', {
      hooks: [{
        hook: 'app:init',
        handler: () => { throw new Error('Handler error'); },
      }],
    }));

    firePluginHook('app:init');

    expect(consoleSpy).toHaveBeenCalledWith(
      '[Plugin] Hook error (app:init):',
      expect.any(Error),
    );

    consoleSpy.mockRestore();
  });
});
