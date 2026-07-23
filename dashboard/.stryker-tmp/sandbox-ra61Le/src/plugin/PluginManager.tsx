/**
 * PluginManager — Renders registered plugin panels and widgets
 * =============================================================
 * Provides a route wrapper for all plugin-registered panels,
 * renders toolbar widgets, and dispatches lifecycle hooks.
 */
// @ts-nocheck


import React, { useEffect, useMemo } from 'react';
import { Route, Routes } from 'react-router-dom';
import { usePluginRegistry, firePluginHook } from './pluginRegistry';

/* ─── Plugin Panel Routes ─────────────────────────────────── */

const PluginPanelRoutes: React.FC = () => {
  const panels = usePluginRegistry(s => s.panels);

  if (panels.length === 0) return null;

  return (
    <Routes>
      {panels.map(panel => (
        <Route
          key={panel.path}
          path={panel.path.replace('/plugins/', '')}
          element={<panel.component />}
        />
      ))}
    </Routes>
  );
};

/* ─── Sidebar Plugin Items ────────────────────────────────── */

export interface SidebarPluginItem {
  path: string;
  label: string;
  icon: string;
}

export function usePluginSidebarItems(): SidebarPluginItem[] {
  const panels = usePluginRegistry(s => s.panels);
  return useMemo(
    () => panels.map(p => ({ path: p.path, label: p.label, icon: p.icon })),
    [panels],
  );
}

/* ─── Command Palette Integration ─────────────────────────── */

export interface PluginCommand {
  id: string;
  label: string;
  icon?: string;
  category?: string;
  execute: () => void;
}

export function usePluginCommands(): PluginCommand[] {
  const commands = usePluginRegistry(s => s.commands);
  return useMemo(
    () => commands.map(c => ({
      id: c.id,
      label: c.label,
      icon: c.icon,
      category: c.category,
      execute: c.execute,
    })),
    [commands],
  );
}

/* ─── Lifecycle Dispatcher ────────────────────────────────── */

/**
 * Fires plugin hooks at app lifecycle events.
 * Include this in App.tsx.
 */
export const PluginLifecycleDispatcher: React.FC = () => {
  useEffect(() => {
    // Fire init hooks after mount
    firePluginHook('app:init', { timestamp: Date.now() });
  }, []);

  return null;
};

/* ─── Toolbar Widget Renderer ─────────────────────────────── */

interface ToolbarWidgetRendererProps {
  position: 'sidebar-top' | 'sidebar-bottom' | 'statusbar-left' | 'statusbar-right';
}

export const ToolbarWidgetRenderer: React.FC<ToolbarWidgetRendererProps> = ({ position }) => {
  const widgets = usePluginRegistry(s => s.widgets);
  const positionWidgets = useMemo(
    () => widgets.filter(w => w.position === position).sort((a, b) => (a.order ?? 100) - (b.order ?? 100)),
    [widgets, position],
  );

  if (positionWidgets.length === 0) return null;

  return (
    <>
      {positionWidgets.map(w => (
        <w.component key={w.id} />
      ))}
    </>
  );
};

export default PluginPanelRoutes;
