/**
 * PluginPage — Plugin Manager
 * =============================
 * Lists all registered plugins with enable/disable toggles,
 * version info, manifest details, and unregister button.
 * Users can manage their plugin set from here.
 */
// @ts-nocheck


import React, { useCallback } from 'react';
import { usePluginRegistry } from '../plugin/pluginRegistry';
import { useUiStore } from '../stores/uiStore';

/* ─── Plugin Card ──────────────────────────────────────────── */

const PluginCard: React.FC<{ id: string }> = ({ id }) => {
  const { getPlugin, enable, disable, unregister } = usePluginRegistry();
  const { addToast } = useUiStore();

  const entry = getPlugin(id);
  if (!entry) return null;

  const { definition: plugin, enabled, loadedAt } = entry;

  const handleToggle = useCallback(() => {
    if (enabled) {
      disable(id);
      addToast(`🔌 ${plugin.manifest.name} 비활성화됨`, 'info');
    } else {
      enable(id);
      addToast(`🔌 ${plugin.manifest.name} 활성화됨`, 'success');
    }
  }, [id, enabled, plugin.manifest.name, enable, disable, addToast]);

  const handleUnregister = useCallback(() => {
    if (confirm(`"${plugin.manifest.name}" 플러그인을 제거하시겠습니까?`)) {
      unregister(id);
      addToast(`🗑️ ${plugin.manifest.name} 제거됨`, 'info');
    }
  }, [id, plugin.manifest.name, unregister, addToast]);

  const loadedDate = new Date(loadedAt).toLocaleString('ko-KR');

  return (
    <div className={`plugin-card glass-panel ${enabled ? '' : 'disabled'}`}>
      <div className="plugin-card-header">
        <span className="plugin-card-icon">{plugin.manifest.icon || '🔌'}</span>
        <div className="plugin-card-info">
          <span className="plugin-card-name">{plugin.manifest.name}</span>
          <span className="plugin-card-id">@{plugin.manifest.id}</span>
          <span className="plugin-card-version">v{plugin.manifest.version}</span>
        </div>
        <label className="plugin-toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={handleToggle}
          />
          <span className="plugin-toggle-slider" />
        </label>
      </div>

      <p className="plugin-card-desc">{plugin.manifest.description}</p>

      <div className="plugin-card-meta">
        {plugin.manifest.author && (
          <span className="plugin-meta-item">👤 {plugin.manifest.author}</span>
        )}
        <span className="plugin-meta-item">📦 {loadedDate}</span>
        {plugin.panels && <span className="plugin-meta-item">📄 {plugin.panels.length} panels</span>}
        {plugin.commands && <span className="plugin-meta-item">⌨ {plugin.commands.length} commands</span>}
        {plugin.hooks && <span className="plugin-meta-item">🔗 {plugin.hooks.length} hooks</span>}
        {plugin.widgets && <span className="plugin-meta-item">🧩 {plugin.widgets.length} widgets</span>}
      </div>

      <div className="plugin-card-actions">
        {plugin.manifest.homepage && (
          <a
            href={plugin.manifest.homepage}
            target="_blank"
            rel="noopener noreferrer"
            className="glass-btn small"
          >
            🌐 홈페이지
          </a>
        )}
        <button className="glass-btn small" onClick={handleUnregister} style={{ color: '#f7768e' }}>
          🗑️ 제거
        </button>
      </div>
    </div>
  );
};

/* ─── PluginPage ───────────────────────────────────────────── */

const PluginPage: React.FC = () => {
  const getAllPlugins = usePluginRegistry(s => s.getAllPlugins);
  const plugins = getAllPlugins();

  return (
    <div className="page-container full-height-page">
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2>🔌 플러그인 <span>Extensions</span></h2>
            <p className="page-subtitle">
              대시보드 기능을 확장하는 플러그인을 관리합니다.
              플러그인은 사이드바 항목, 명령어, 패널, 훅을 등록할 수 있습니다.
            </p>
          </div>
          <span className="plugin-count-badge">{plugins.length} plugins</span>
        </div>
      </div>

      {plugins.length === 0 ? (
        <div className="plugin-empty">
          <span className="plugin-empty-icon">🔌</span>
          <span>등록된 플러그인이 없습니다</span>
          <span className="plugin-empty-hint">API 또는 로컬 코드가 플러그인을 등록하면 여기에 표시됩니다</span>
        </div>
      ) : (
        <div className="plugin-grid">
          {plugins.map(entry => (
            <PluginCard key={entry.definition.manifest.id} id={entry.definition.manifest.id} />
          ))}
        </div>
      )}
    </div>
  );
};

export default PluginPage;
