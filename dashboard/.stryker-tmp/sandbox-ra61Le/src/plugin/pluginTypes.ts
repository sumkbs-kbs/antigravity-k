/**
 * Plugin System Types (TypeScript)
 * =================================
 * Core type definitions for the Antigravity-K plugin architecture.
 * Supports custom panels, hooks, commands, sidebar items, and toolbar widgets.
 */
// @ts-nocheck


import type { ReactNode } from 'react';

/* ─── Plugin Manifest ─────────────────────────────────────── */

export interface PluginManifest {
  /** Unique plugin ID (e.g. 'my-plugin') */
  id: string;
  /** Human-readable name */
  name: string;
  /** Version string (semver) */
  version: string;
  /** Plugin description */
  description: string;
  /** Author name or org */
  author?: string;
  /** Icon emoji or URL */
  icon?: string;
  /** Minimum dashboard version required */
  minAppVersion?: string;
  /** Optional homepage URL */
  homepage?: string;
}

/* ─── Panel Registration ──────────────────────────────────── */

export interface PanelRegistration {
  /** Route path (e.g. '/plugins/my-panel') */
  path: string;
  /** Panel component */
  component: React.FC;
  /** Navigation label (shown in sidebar) */
  label: string;
  /** Emoji icon for sidebar */
  icon: string;
  /** Optional: sort order in sidebar (lower = higher) */
  order?: number;
}

/* ─── Command Registration ────────────────────────────────── */

export interface CommandRegistration {
  /** Unique command ID */
  id: string;
  /** Display name in command palette */
  label: string;
  /** Optional: keyboard shortcut keys */
  keys?: string[];
  /** Execute handler */
  execute: () => void;
  /** Optional: icon */
  icon?: string;
  /** Optional: category for grouping */
  category?: string;
}

/* ─── Hook Types ──────────────────────────────────────────── */

export type HookType =
  | 'app:init'          /** App initialization complete */
  | 'app:beforeMount'   /** Before first render */
  | 'file:open'         /** File opened in editor */
  | 'file:save'         /** File saved */
  | 'file:change'       /** File content changed */
  | 'chat:send'         /** Message sent to chat */
  | 'chat:response'     /** Response received */
  | 'git:commit'        /** Git commit made */
  | 'tool:start'        /** Tool execution started */
  | 'tool:end'          /** Tool execution ended */
  ;

export interface HookRegistration {
  /** Which hook to subscribe to */
  hook: HookType;
  /** Handler function */
  handler: (data?: any) => void;
  /** Optional: priority (higher = runs first, default 0) */
  priority?: number;
}

/* ─── Toolbar Widget ──────────────────────────────────────── */

export interface ToolbarWidgetRegistration {
  id: string;
  /** Widget component (small icon/button for toolbar area) */
  component: React.FC;
  /** Position hint: 'sidebar-top' | 'sidebar-bottom' | 'statusbar-left' | 'statusbar-right' */
  position: 'sidebar-top' | 'sidebar-bottom' | 'statusbar-left' | 'statusbar-right';
  /** Sort order within position */
  order?: number;
}

/* ─── Full Plugin Definition ──────────────────────────────── */

export interface PluginDefinition {
  /** Plugin metadata */
  manifest: PluginManifest;
  /** Optional: method called when plugin is loaded */
  onLoad?: () => void;
  /** Optional: method called when plugin is unloaded */
  onUnload?: () => void;
  /** Panels to register */
  panels?: PanelRegistration[];
  /** Commands to register */
  commands?: CommandRegistration[];
  /** Hooks to subscribe to */
  hooks?: HookRegistration[];
  /** Toolbar widgets to register */
  widgets?: ToolbarWidgetRegistration[];
}

/* ─── Plugin Store Types ──────────────────────────────────── */

export interface PluginEntry {
  definition: PluginDefinition;
  enabled: boolean;
  loadedAt: number;
}

export interface PluginRegistryState {
  /** All registered plugins (keyed by id) */
  plugins: Record<string, PluginEntry>;
  /** Flat lists for quick lookup */
  panels: PanelRegistration[];
  commands: CommandRegistration[];
  hooks: HookRegistration[];
  widgets: ToolbarWidgetRegistration[];

  /** Actions */
  register: (plugin: PluginDefinition) => boolean;
  unregister: (id: string) => boolean;
  enable: (id: string) => void;
  disable: (id: string) => void;
  getPlugin: (id: string) => PluginEntry | undefined;
  getAllPlugins: () => PluginEntry[];
}
