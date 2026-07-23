/**
 * Plugin Registry Store (Zustand)
 * =================================
 * Central registry for all plugins. Manages registration lifecycle,
 * enables/disables, and maintains flat lookup lists for panels,
 * commands, hooks, and widgets used by the UI.
 */

import { create } from 'zustand';
import type {
  PluginDefinition,
  PluginEntry,
  PluginRegistryState,
  PanelRegistration,
  CommandRegistration,
  HookRegistration,
  ToolbarWidgetRegistration,
} from './pluginTypes';

/* ─── Storage key ──────────────────────────────────────────── */

const ENABLED_KEY = 'agk_plugins_enabled';

function loadEnabled(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(ENABLED_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return {};
}

function saveEnabled(enabled: Record<string, boolean>) {
  try {
    localStorage.setItem(ENABLED_KEY, JSON.stringify(enabled));
  } catch { /* ignore */ }
}

/* ─── Rebuild flat lists ──────────────────────────────────── */

function rebuildLists(plugins: Record<string, PluginEntry>): {
  panels: PanelRegistration[];
  commands: CommandRegistration[];
  hooks: HookRegistration[];
  widgets: ToolbarWidgetRegistration[];
} {
  const panels: PanelRegistration[] = [];
  const commands: CommandRegistration[] = [];
  const hooks: HookRegistration[] = [];
  const widgets: ToolbarWidgetRegistration[] = [];

  for (const entry of Object.values(plugins)) {
    if (!entry.enabled) continue;
    const def = entry.definition;

    if (def.panels) panels.push(...def.panels);
    if (def.commands) commands.push(...def.commands);
    if (def.hooks) hooks.push(...def.hooks);
    if (def.widgets) widgets.push(...def.widgets);
  }

  // Sort panels by order
  panels.sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
  // Sort hooks by priority (descending)
  hooks.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
  // Sort widgets by order
  widgets.sort((a, b) => (a.order ?? 100) - (b.order ?? 100));

  return { panels, commands, hooks, widgets };
}

/* ─── Store ────────────────────────────────────────────────── */

const enabledState = loadEnabled();

export const usePluginRegistry = create<PluginRegistryState>((set, get) => ({
  plugins: {},
  panels: [],
  commands: [],
  hooks: [],
  widgets: [],

  register: (plugin) => {
    const state = get();
    if (state.plugins[plugin.manifest.id]) {
      console.warn(`[Plugin] Already registered: ${plugin.manifest.id}`);
      return false;
    }

    const wasEnabled = enabledState[plugin.manifest.id] !== false;
    const entry: PluginEntry = {
      definition: plugin,
      enabled: wasEnabled,
      loadedAt: Date.now(),
    };

    // Call onLoad if plugin is enabled
    if (wasEnabled) {
      try { plugin.onLoad?.(); } catch (e) {
        console.error(`[Plugin] onLoad error (${plugin.manifest.id}):`, e);
      }
    }

    const plugins = { ...state.plugins, [plugin.manifest.id]: entry };
    const lists = rebuildLists(plugins);
    set({ plugins, ...lists });

    console.log(`[Plugin] Registered: ${plugin.manifest.id} v${plugin.manifest.version}`);
    return true;
  },

  unregister: (id) => {
    const state = get();
    const entry = state.plugins[id];
    if (!entry) return false;

    // Call onUnload
    try { entry.definition.onUnload?.(); } catch (e) {
      console.error(`[Plugin] onUnload error (${id}):`, e);
    }

    const plugins = { ...state.plugins };
    delete plugins[id];
    const lists = rebuildLists(plugins);

    // Clean up enabled state
    const enabled = loadEnabled();
    delete enabled[id];
    saveEnabled(enabled);

    set({ plugins, ...lists });
    console.log(`[Plugin] Unregistered: ${id}`);
    return true;
  },

  enable: (id) => {
    const state = get();
    const entry = state.plugins[id];
    if (!entry || entry.enabled) return;

    // Call onLoad
    try { entry.definition.onLoad?.(); } catch (e) {
      console.error(`[Plugin] onLoad error (${id}):`, e);
    }

    const plugins = {
      ...state.plugins,
      [id]: { ...entry, enabled: true },
    };
    const lists = rebuildLists(plugins);
    set({ plugins, ...lists });

    // Persist
    const enabled = loadEnabled();
    enabled[id] = true;
    saveEnabled(enabled);
  },

  disable: (id) => {
    const state = get();
    const entry = state.plugins[id];
    if (!entry || !entry.enabled) return;

    // Call onUnload
    try { entry.definition.onUnload?.(); } catch (e) {
      console.error(`[Plugin] onUnload error (${id}):`, e);
    }

    const plugins = {
      ...state.plugins,
      [id]: { ...entry, enabled: false },
    };
    const lists = rebuildLists(plugins);
    set({ plugins, ...lists });

    // Persist
    const enabled = loadEnabled();
    enabled[id] = false;
    saveEnabled(enabled);
  },

  getPlugin: (id) => get().plugins[id],

  getAllPlugins: () => Object.values(get().plugins),
}));

/* ─── Lifecycle: Fire hooks ────────────────────────────────── */

/**
 * Fire a hook event to all registered plugin handlers.
 * Call this from app code when events occur.
 */
import type { HookType } from './pluginTypes';

export function firePluginHook(hook: HookType, data?: any) {
  const state = usePluginRegistry.getState();
  for (const reg of state.hooks) {
    if (reg.hook === hook) {
      try {
        reg.handler(data);
      } catch (e) {
        console.error(`[Plugin] Hook error (${hook}):`, e);
      }
    }
  }
}
