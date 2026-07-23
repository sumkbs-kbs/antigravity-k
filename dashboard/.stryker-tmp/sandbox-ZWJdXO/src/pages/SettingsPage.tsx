/**
 * SettingsPage — System Settings
 * ================================
 * Ported from Vanilla JS. API keys, model selection, search engine, cost control.
 */
// @ts-nocheck


import React, { useEffect, useState } from 'react';
import { GlassPanel } from '../components/shared';
import { useThemeStore } from '../stores/themeStore';
import { useLocalHistoryStore } from '../stores/localHistoryStore';

interface ServerConfig {
  host?: string;
  port?: string;
}

interface ModelConfig {
  provider?: string;
  name?: string;
}

interface SettingsData {
  api_keys?: Record<string, string>;
  server?: ServerConfig;
  model?: ModelConfig;
}

const PROVIDERS = [
  { key: 'OPENROUTER_API_KEY', label: 'OpenRouter', icon: '🌐', hint: 'openrouter.ai/keys' },
  { key: 'NVIDIA_API_KEY', label: 'NVIDIA NIM (무료)', icon: '🟢', hint: 'build.nvidia.com' },
  { key: 'OPENAI_API_KEY', label: 'OpenAI', icon: '🔵', hint: 'platform.openai.com/api-keys' },
  { key: 'GEMINI_API_KEY', label: 'Google Gemini', icon: '✨', hint: 'aistudio.google.com/apikey' },
  { key: 'ZAI_API_KEY', label: 'ZAI / Zhipu GLM', icon: '🧠', hint: 'open.bigmodel.cn' },
  { key: 'ANTHROPIC_API_KEY', label: 'Anthropic Claude', icon: '🟣', hint: 'console.anthropic.com' },
];

const THEME_COLORS = ['#7c6aef', '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#a855f7', '#3b82f6', '#14b8a6'];

const FONT_SIZES = [12, 13, 14, 15, 16, 18, 20];

const SettingsPage: React.FC = () => {
  const { accentColor, fontSize, showMinimap, wordWrap, tabSize, setPref, reset: resetTheme } = useThemeStore();
  const { autoSaveEnabled, setAutoSaveEnabled } = useLocalHistoryStore();
  const [config, setConfig] = useState<SettingsData>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [defaultModel, setDefaultModel] = useState('');
  const [searchEngine, setSearchEngine] = useState('searxng');
  const [dailyBudget, setDailyBudget] = useState('50');
  const [hourlyLimit, setHourlyLimit] = useState('100');
  const [statusMsg, setStatusMsg] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedSettings = JSON.parse(localStorage.getItem('agk_user_settings') || '{}');
    fetch('/api/settings')
      .then(r => r.json())
      .then((data: { settings?: SettingsData }) => {
        const cfg = data.settings || {};
        setConfig(cfg);
        setDefaultModel(savedSettings.default_model || cfg.model?.name || '');
        setSearchEngine(savedSettings.search_engine || 'searxng');
        setDailyBudget(savedSettings.daily_budget_usd || '50');
        setHourlyLimit(savedSettings.hourly_action_limit || '100');
        setApiKeys(savedSettings);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    const settings: Record<string, string> = { ...apiKeys };
    settings.default_model = defaultModel;
    settings.search_engine = searchEngine;
    settings.daily_budget_usd = dailyBudget;
    settings.hourly_action_limit = hourlyLimit;

    localStorage.setItem('agk_user_settings', JSON.stringify(settings));
    setStatusMsg('⏳ 저장 중...');
    setSaving(true);

    try {
      const res = await fetch('/api/settings/env', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Access-Pin': localStorage.getItem('ag_access_pin') || '0000',
        },
        body: JSON.stringify(settings),
      });
      const data = await res.json();
      if (data.ok) {
        setStatusMsg(`✅ 저장 완료! ${data.updated || 0}개 항목이 .env에 저장되었습니다.`);
      } else {
        setStatusMsg(`⚠️ ${data.error || data.detail || '저장 실패 — PIN을 확인하세요'}`);
      }
    } catch (err: any) {
      setStatusMsg(`⚠️ localStorage에 저장됨 (.env 동기화 실패: ${err.message})`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (confirm('모든 설정을 초기화하시겠습니까?')) {
      localStorage.removeItem('agk_user_settings');
      window.location.reload();
    }
  };

  if (loading) {
    return <div className="page-container"><div className="loading-state">설정 불러오는 중...</div></div>;
  }

  return (
    <div className="settings-page" style={{ maxWidth: 800 }}>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <h2>시스템 설정 <span>Settings</span></h2>
        <p className="page-subtitle">API 키, 모델, 검색 엔진, 비용 제어를 설정합니다.</p>
      </div>

      <div id="settings-container" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* 1. API Keys */}
        <GlassPanel title="🔑 API 키 설정" variant="section" className="settings-section">
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            사용할 프로바이더의 API 키를 입력하세요. 입력된 키는 서버 재시작 후 적용됩니다.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {PROVIDERS.map(p => {
              const isSet = !!apiKeys[p.key];
              return (
                <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 140, flexShrink: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{p.icon} {p.label}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{p.hint}</div>
                  </div>
                  <input
                    type="password"
                    className="glass-input"
                    placeholder={isSet ? '•••••••• (재입력 시 덮어쓰기)' : 'API 키 입력'}
                    value={apiKeys[p.key] || ''}
                    onChange={e => setApiKeys(prev => ({ ...prev, [p.key]: e.target.value }))}
                    style={{ flex: 1, fontSize: 13, fontFamily: "'JetBrains Mono', monospace", padding: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }}
                  />
                  <div style={{ width: 80, textAlign: 'right' }}>
                    {isSet
                      ? <span style={{ color: '#10b981', fontSize: 11 }}>✓ 설정됨</span>
                      : <span style={{ color: '#565f89', fontSize: 11 }}>⚪ 미설정</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </GlassPanel>

        {/* 2. Default Model */}
        <GlassPanel title="🤖 기본 모델" variant="section" className="settings-section">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 140, fontSize: 13, fontWeight: 500, flexShrink: 0 }}>기본 추론 모델</div>
            <input
              type="text"
              className="glass-input"
              placeholder="예: qwen3.6:latest, openai/gpt-4o-mini"
              value={defaultModel}
              onChange={e => setDefaultModel(e.target.value)}
              style={{ flex: 1, fontSize: 13, padding: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }}
            />
          </div>
        </GlassPanel>

        {/* 3. Search Engine — Toggle Switch */}
        <GlassPanel title="🔍 웹 검색 엔진" variant="section" className="settings-section">
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
            기본 검색 엔진을 선택하세요. 변경 사항은 즉시 적용됩니다.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {[
              { id: 'searxng', label: 'SearxNG', desc: '메타 검색 — Google+Bing+DDG 집계, 로컬' },
              { id: 'duckduckgo', label: 'DuckDuckGo', desc: '단일 엔진, 간단, 추가 설정 불필요' },
              { id: 'jina', label: 'Jina AI', desc: '시맨틱 검색, AI 친화적 결과' },
            ].map(engine => (
              <label key={engine.id} className="toggle-switch">
                <input
                  type="radio"
                  name="search_engine"
                  value={engine.id}
                  checked={searchEngine === engine.id}
                  onChange={() => setSearchEngine(engine.id)}
                />
                <span className="toggle-track" />
                <span className="toggle-label">
                  {engine.label}
                  <small>{engine.desc}</small>
                </span>
              </label>
            ))}
          </div>
        </GlassPanel>

        {/* 4. Cost Control */}
        <GlassPanel title="💰 비용 제어" variant="section" className="settings-section">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 160, fontSize: 13, fontWeight: 500, flexShrink: 0 }}>일일 예산 (USD)</div>
              <input type="number" className="glass-input" value={dailyBudget} onChange={e => setDailyBudget(e.target.value)}
                style={{ width: 100, padding: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>초과 시 LLM 호출 차단</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 160, fontSize: 13, fontWeight: 500, flexShrink: 0 }}>시간당 액션 한도</div>
              <input type="number" className="glass-input" value={hourlyLimit} onChange={e => setHourlyLimit(e.target.value)}
                style={{ width: 100, padding: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>분당 호출 수 제한</span>
            </div>
          </div>
        </GlassPanel>

        {/* 5. Local History Settings */}
        <GlassPanel title="📜 로컬 히스토리" variant="section" className="settings-section">
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            파일 변경 내역을 자동으로 저장하여 이전 상태로 되돌리거나 비교할 수 있습니다.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={autoSaveEnabled}
                onChange={e => setAutoSaveEnabled(e.target.checked)}
              />
              <span className="toggle-track" />
              <span className="toggle-label">
                자동 스냅샷 저장
                <small>파일이 변경될 때마다 현재 상태를 히스토리에 저장합니다</small>
              </span>
            </label>
          </div>
        </GlassPanel>

        {/* 6. Theme Customization */}
        <GlassPanel title="🎨 테마 설정" variant="section" className="settings-section">
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
            에디터와 인터페이스의 모양을 커스터마이즈합니다.
          </p>

          {/* Accent Color */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 8 }}>
              강조 색상
            </label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {THEME_COLORS.map(color => (
                <button
                  key={color}
                  className="theme-color-swatch"
                  onClick={() => setPref('accentColor', color)}
                  style={{
                    width: 32, height: 32, borderRadius: '50%',
                    background: color,
                    border: accentColor === color ? '3px solid #fff' : '3px solid transparent',
                    boxShadow: accentColor === color ? `0 0 12px ${color}` : 'none',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  title={color}
                />
              ))}
            </div>
          </div>

          {/* Font Size */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 8 }}>
              에디터 폰트 크기
            </label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {FONT_SIZES.map(size => (
                <button
                  key={size}
                  className={`glass-btn small ${fontSize === size ? 'primary' : ''}`}
                  onClick={() => setPref('fontSize', size)}
                  style={{ fontSize: size > 14 ? 12 : 11 }}
                >
                  {size}px
                </button>
              ))}
            </div>
          </div>

          {/* Editor Options */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label className="toggle-switch">
              <input type="checkbox" checked={showMinimap} onChange={e => setPref('showMinimap', e.target.checked)} />
              <span className="toggle-track" />
              <span className="toggle-label">미니맵 표시</span>
            </label>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>탭 크기</span>
              <select
                className="glass-select"
                value={tabSize}
                onChange={e => setPref('tabSize', parseInt(e.target.value))}
                style={{ minWidth: 80 }}
              >
                <option value={2}>2</option>
                <option value={4}>4</option>
                <option value={8}>8</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>자동 줄바꿈</span>
              <select
                className="glass-select"
                value={wordWrap}
                onChange={e => setPref('wordWrap', e.target.value as 'on' | 'off')}
                style={{ minWidth: 80 }}
              >
                <option value="on">On</option>
                <option value="off">Off</option>
              </select>
            </div>
          </div>

          {/* Reset Theme */}
          <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--glass-border)' }}>
            <button className="glass-btn small" onClick={resetTheme}>
              🎨 테마 초기화
            </button>
          </div>
        </GlassPanel>

        {/* 6. Server Config (read-only) */}
        <GlassPanel title="🖥 서버 구성 (읽기 전용)" variant="section" className="settings-section" style={{ opacity: 0.8 }}>
          <div style={{ opacity: 0.8 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 12, alignItems: 'center', fontSize: 14 }}>
              <div style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>호스트</div>
              <div>{config.server?.host || '127.0.0.1'}</div>
              <div style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>포트</div>
              <div>{config.server?.port || '8000'}</div>
              <div style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>API 엔진</div>
              <div>{config.model?.provider || 'openrouter'}</div>
            </div>
          </div>
        </GlassPanel>

        {/* Save / Reset */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', alignItems: 'center' }}>
          {statusMsg && (
            <div style={{ fontSize: 12, flex: 1, textAlign: 'left', minHeight: 18 }}
              dangerouslySetInnerHTML={{ __html: statusMsg }} />
          )}
          <button className="glass-btn" onClick={handleReset}>
            🗑️ 초기화
          </button>
          <button className={`glass-btn primary save-anim ${saving ? 'saving' : ''}`} onClick={handleSave} disabled={saving}>
            {saving ? (
              <><span className="spinner spinner-sm" /> 저장 중...</>
            ) : (
              '💾 설정 저장'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
