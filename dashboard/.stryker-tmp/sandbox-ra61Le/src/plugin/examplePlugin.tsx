/**
 * Example Plugin -- Built-in demo for the plugin system
 * Shows panel, command palette, and app lifecycle hooks.
 */
// @ts-nocheck


import React from 'react';
import type { PluginDefinition } from './pluginTypes';
import { usePluginRegistry } from './pluginRegistry';
import { useUiStore } from '../stores/uiStore';

const HelloWorldPanel: React.FC = () => {
  const { addToast } = useUiStore();
  const plugins = usePluginRegistry(s => s.plugins);
  const pluginCount = Object.keys(plugins).length;

  return (
    <div className="page-container full-height-page">
      <div className="page-header">
        <h2>Hello from Plugin System!</h2>
        <p className="page-subtitle">This panel was registered through the plugin system.</p>
      </div>
      <div className="hello-plugin-content">
        <div className="hello-plugin-stats glass-panel">
          <div className="hello-stat">
            <span className="hello-stat-value">{pluginCount}</span>
            <span className="hello-stat-label">Registered Plugins</span>
          </div>
          <div className="hello-stat">
            <span className="hello-stat-value">v1.0</span>
            <span className="hello-stat-label">Plugin API</span>
          </div>
          <div className="hello-stat">
            <span className="hello-stat-value">3</span>
            <span className="hello-stat-label">Panel + Command + Hooks</span>
          </div>
        </div>
        <div className="hello-plugin-info glass-panel">
          <h4>How to Use</h4>
          <ol style={{ lineHeight: 2, paddingLeft: 20, margin: 0 }}>
            <li><code>pluginRegistry.register(plugin)</code> -- register a plugin</li>
            <li>Panel link appears in sidebar automatically</li>
            <li>Commands searchable in command palette (Cmd+K)</li>
            <li>Hooks respond to app lifecycle events</li>
          </ol>
          <div className="hello-plugin-actions">
            <button
              className="glow-btn"
              onClick={() => addToast('Plugin API: addToast works!', 'success')}
            >
              Test Toast
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export const examplePlugin: PluginDefinition = {
  manifest: {
    id: 'example-hello-world',
    name: 'Hello World',
    version: '1.0.0',
    description: 'Plugin system demo with panel, commands, and hooks.',
    author: 'Antigravity-K',
    icon: 'W',
  },
  onLoad: () => {
    console.log('[ExamplePlugin] Loaded!');
  },
  onUnload: () => {
    console.log('[ExamplePlugin] Unloaded!');
  },
  panels: [
    {
      path: '/plugins/hello-world',
      component: HelloWorldPanel,
      label: 'Hello Plugin',
      icon: 'W',
      order: 1,
    },
  ],
  commands: [
    {
      id: 'example:show-toast',
      label: 'Plugin: Show test toast',
      icon: 'T',
      category: 'Plugin',
      execute: () => {
        useUiStore.getState().addToast('Plugin command executed!', 'success');
      },
    },
    {
      id: 'example:open-panel',
      label: 'Plugin: Open Hello World panel',
      icon: 'W',
      category: 'Plugin',
      execute: () => {
        window.dispatchEvent(new CustomEvent('agk:navigate', { detail: '/plugins/hello-world' }));
      },
    },
  ],
  hooks: [
    {
      hook: 'app:init',
      handler: () => {
        console.log('[ExamplePlugin] App initialized!');
      },
    },
    {
      hook: 'chat:send',
      handler: (data) => {
        console.log('[ExamplePlugin] Chat message sent:', data);
      },
    },
  ],
};
