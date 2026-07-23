/**
 * PublishTab — Skill Publishing Dashboard
 * =========================================
 * Phase 1 D17: Publish local skills to npm registry or GitHub PR.
 * Provides validation preview, npm publish (dry-run + real), GitHub PR forms,
 * and publish history tracking (localStorage).
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useUiStore } from '../../stores/uiStore';
import { LocalSkill, PublishResult, PublishHistoryEntry, esc } from './types';
import EmptyState from './EmptyState';

type PublishMode = 'npm' | 'github';
type Step = 'idle' | 'validating' | 'publishing' | 'done' | 'error';

export const HISTORY_KEY = 'agk_publish_history';
export const MAX_HISTORY = 50;

export function loadHistory(): PublishHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

export function saveHistory(entries: PublishHistoryEntry[]): void {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, MAX_HISTORY)));
  } catch {
    // localStorage full — silently ignore
  }
}

export function buildEntry(result: PublishResult, dryRun: boolean): PublishHistoryEntry {
  return {
    id: `pub_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
    skill_name: result.skill_name,
    action: result.action,
    success: result.success,
    timestamp: new Date().toISOString(),
    version: result.version,
    package_name: result.package_name,
    dry_run: dryRun,
    summary: result.summary,
    errors: result.errors,
    warnings: result.warnings,
    npm_url: result.npm_url,
    pr_url: result.pr_url,
  };
}

const POLL_INTERVAL_MS = 15000;

const PublishTab: React.FC = () => {
  const [localSkills, setLocalSkills] = useState<LocalSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [publishMode, setPublishMode] = useState<PublishMode>('npm');
  const [step, setStep] = useState<Step>('idle');
  const [result, setResult] = useState<PublishResult | null>(null);
  const [ghRepo, setGhRepo] = useState('ssak-comp/antigravity-k');
  const [ghDraft, setGhDraft] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [npmTag, setNpmTag] = useState('latest');
  const [history, setHistory] = useState<PublishHistoryEntry[]>(() => loadHistory());
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [expandedEntryId, setExpandedEntryId] = useState<string | null>(null);
  const [newSkillsDetected, setNewSkillsDetected] = useState(false);
  const [silentLoading, setSilentLoading] = useState(false);
  const skillCountRef = useRef(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadLocalSkills = useCallback(async (silent = false) => {
    if (silent) {
      setSilentLoading(true);
    } else {
      setLoading(true);
    }
    try {
      const res = await fetch('/api/system/skills/local');
      const data = await res.json();
      const skills: LocalSkill[] = data.skills || [];

      const prevCount = skillCountRef.current;
      if (silent && prevCount > 0 && skills.length !== prevCount) {
        setNewSkillsDetected(true);
      }

      setLocalSkills(skills);
      skillCountRef.current = skills.length;
    } catch {
      setLocalSkills([]);
    } finally {
      setLoading(false);
      setSilentLoading(false);
    }
  }, []);

  useEffect(() => { loadLocalSkills(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-polling: silently check for new skills every 15s
  useEffect(() => {
    pollingRef.current = setInterval(() => {
      loadLocalSkills(true);
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handlePublish = useCallback(async () => {
    if (!selectedSkill) return;
    setStep('publishing');
    setResult(null);

    try {
      const endpoint = publishMode === 'npm'
        ? '/api/system/skills/publish-npm'
        : '/api/system/skills/publish-github';

      const body: Record<string, any> = {
        skill_name: selectedSkill,
        dry_run: dryRun,
      };
      if (publishMode === 'npm') {
        body.tag = npmTag;
      } else {
        body.repo = ghRepo;
        body.draft = ghDraft;
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();

      let publishResult: PublishResult;

      if (data.publish_result) {
        publishResult = data.publish_result;
        setResult(publishResult);
        setStep(publishResult.success ? 'done' : 'error');

        if (publishResult.success) {
          useUiStore.getState().addToast(
            `✅ ${publishMode === 'npm' ? 'npm publish' : 'GitHub PR'} 성공: ${selectedSkill}`,
            'success',
          );
        }
      } else {
        publishResult = {
          success: false,
          action: publishMode === 'npm' ? 'npm_publish' : 'github_pr',
          skill_name: selectedSkill,
          errors: [data.error || 'Unknown error'],
          warnings: [],
          summary: `❌ ${selectedSkill} publish 실패: ${data.error || 'Unknown error'}`,
        };
        setResult(publishResult);
        setStep('error');
      }

      // Save to history
      const entry = buildEntry(publishResult, dryRun);
      setHistory(prev => {
        const updated = [entry, ...prev].slice(0, MAX_HISTORY);
        saveHistory(updated);
        return updated;
      });
    } catch (err) {
      const publishResult: PublishResult = {
        success: false,
        action: publishMode === 'npm' ? 'npm_publish' : 'github_pr',
        skill_name: selectedSkill,
        errors: [String(err)],
        warnings: [],
        summary: `❌ ${selectedSkill} publish 실패: ${err}`,
      };
      setResult(publishResult);
      setStep('error');

      // Save failure to history
      const entry = buildEntry(publishResult, dryRun);
      setHistory(prev => {
        const updated = [entry, ...prev].slice(0, MAX_HISTORY);
        saveHistory(updated);
        return updated;
      });
    }
  }, [selectedSkill, publishMode, dryRun, npmTag, ghRepo, ghDraft]);

  const clearHistory = useCallback(() => {
    setHistory([]);
    setExpandedEntryId(null);
    try { localStorage.removeItem(HISTORY_KEY); } catch { /* ignore */ }
  }, []);

  const selectedSkillData = localSkills.find(s => s.name === selectedSkill);

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleString('ko-KR', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      });
    } catch { return iso; }
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16 }}>📦 Skill Publish</h3>
            <p className="page-subtitle" style={{ margin: '4px 0 0 0' }}>
              로컬 스킬을 npm 레지스트리에 publish하거나 GitHub PR로 제출합니다.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {silentLoading && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                🔄 확인 중...
              </span>
            )}
            {newSkillsDetected && (
              <button
                className="glass-btn primary"
                onClick={() => { setNewSkillsDetected(false); loadLocalSkills(); }}
                style={{
                  gap: 6, padding: '4px 12px', fontSize: 12,
                  animation: 'agk-pulse 2s ease-in-out infinite',
                }}
              >
                ✨ 새 스킬 발견! 새로고침
              </button>
            )}
            <button className="glass-btn" onClick={() => loadLocalSkills()} style={{ gap: 6 }}>
              <span>🔄</span> 새로고침
            </button>
          </div>
        </div>
      </div>

      {/* Local Skills List */}
      {loading ? (
        <div className="skills-loading">🔄 스킬 목록을 불러오는 중...</div>
      ) : localSkills.length === 0 ? (
        <EmptyState
          icon="📦"
          title="Publish 가능한 로컬 스킬이 없습니다."
          subtitle=".agent/skills/ 또는 .agent/skills/market/ 디렉토리에 스킬을 추가하세요."
        />
      ) : (
        <div className="skills-grid" style={{ marginBottom: 24 }}>
          {localSkills.map(skill => (
            <div
              key={skill.name}
              className={`glass-panel skill-card ${selectedSkill === skill.name ? 'selected' : ''}`}
              style={{
                cursor: 'pointer',
                border: selectedSkill === skill.name
                  ? '1px solid var(--accent, #7c6aef)'
                  : '1px solid var(--glass-border, rgba(255,255,255,0.1))',
                transition: 'all 0.2s ease',
              }}
              onClick={() => {
                setSelectedSkill(skill.name);
                setStep('idle');
                setResult(null);
              }}
            >
              <div className="skill-card-header">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 14 }}>{skill.source === 'market' ? '🏪' : '📁'}</span>
                    <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                      {esc(skill.name)}
                    </strong>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                  {skill.valid
                    ? <span className="status-badge active" style={{ fontSize: 10 }}>✅ Valid</span>
                    : <span className="status-badge pending" style={{ fontSize: 10 }}>⚠️ Invalid</span>}
                </div>
              </div>
              <div className="skill-card-meta" style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 11,
                color: 'var(--text-muted)',
              }}>
                <span>
                  {skill.source === 'market' ? '🏪 market/' : '📁 local/'} · v{skill.version} · {skill.tool_count} tools
                </span>
              </div>
              {skill.warnings.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--warning, #d29922)' }}>
                  {skill.warnings.slice(0, 2).map((w, i) => (
                    <div key={i}>⚠️ {esc(w)}</div>
                  ))}
                  {skill.warnings.length > 2 && <div>...and {skill.warnings.length - 2} more</div>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Publish Panel (when a skill is selected) */}
      {selectedSkill && (
        <div className="glass-panel" style={{ padding: 20, marginBottom: 20 }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 15 }}>
            📤 Publish: <strong>{esc(selectedSkill)}</strong>
          </h3>

          {/* Mode Toggle */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button
              className={`glass-btn ${publishMode === 'npm' ? 'primary' : ''}`}
              onClick={() => setPublishMode('npm')}
              style={{ padding: '6px 14px', fontSize: 13 }}
            >
              📦 npm publish
            </button>
            <button
              className={`glass-btn ${publishMode === 'github' ? 'primary' : ''}`}
              onClick={() => setPublishMode('github')}
              style={{ padding: '6px 14px', fontSize: 13 }}
            >
              🔀 GitHub PR
            </button>
          </div>

          {/* Publish Options */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
            {publishMode === 'npm' ? (
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  npm tag:
                  <input
                    type="text"
                    className="glass-input"
                    value={npmTag}
                    onChange={e => setNpmTag(e.target.value)}
                    style={{
                      marginLeft: 8,
                      padding: '4px 10px',
                      width: 100,
                      fontSize: 13,
                      background: 'rgba(0,0,0,0.2)',
                      border: '1px solid var(--glass-border)',
                      color: '#fff',
                      borderRadius: 4,
                    }}
                  />
                </label>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  GitHub Repo:
                  <input
                    type="text"
                    className="glass-input"
                    value={ghRepo}
                    onChange={e => setGhRepo(e.target.value)}
                    style={{
                      marginLeft: 8,
                      padding: '4px 10px',
                      width: 220,
                      fontSize: 13,
                      background: 'rgba(0,0,0,0.2)',
                      border: '1px solid var(--glass-border)',
                      color: '#fff',
                      borderRadius: 4,
                    }}
                    placeholder="org/skills-repo"
                  />
                </label>
                <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <input
                    type="checkbox"
                    checked={ghDraft}
                    onChange={e => setGhDraft(e.target.checked)}
                    style={{ accentColor: '#7c6aef' }}
                  />
                  Draft PR
                </label>
              </div>
            )}

            {/* Dry-run toggle */}
            <label style={{
              fontSize: 13,
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}>
              <input
                type="checkbox"
                checked={dryRun}
                onChange={e => setDryRun(e.target.checked)}
                style={{ accentColor: '#7c6aef' }}
              />
              <span>🔄 Dry-run (실제 publish 없이 검증만 수행)</span>
            </label>
          </div>

          {/* Publish Button */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="glass-btn primary"
              onClick={handlePublish}
              disabled={step === 'publishing'}
              style={{ padding: '8px 20px', fontSize: 14 }}
            >
              {step === 'publishing'
                ? '⏳ Publishing...'
                : dryRun
                  ? '🔍 Validate & Dry-run'
                  : '🚀 Publish'}
            </button>
            {result && (
              <button
                className="glass-btn"
                onClick={() => { setStep('idle'); setResult(null); }}
                style={{ padding: '8px 16px', fontSize: 13 }}
              >
                ✕ Clear
              </button>
            )}
          </div>

          {/* Result Display */}
          {result && (
            <div style={{
              marginTop: 16,
              padding: 14,
              borderRadius: 8,
              background: result.success
                ? 'rgba(63,185,80,0.08)'
                : 'rgba(248,81,73,0.08)',
              border: `1px solid ${result.success ? 'rgba(63,185,80,0.2)' : 'rgba(248,81,73,0.2)'}`,
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              <div style={{
                fontWeight: 600,
                marginBottom: 8,
                color: result.success ? '#3fb950' : '#f85149',
              }}>
                {result.success ? '✅ Success' : '❌ Failed'}
              </div>
              <div>{result.summary}</div>
              {result.errors.length > 0 && (
                <div style={{ marginTop: 8, color: '#f85149' }}>
                  {result.errors.map((e, i) => <div key={i}>• {e}</div>)}
                </div>
              )}
              {result.warnings.length > 0 && (
                <div style={{ marginTop: 8, color: '#d29922' }}>
                  {result.warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
                </div>
              )}
              {result.npm_url && (
                <div style={{ marginTop: 8 }}>
                  <a href={result.npm_url} target="_blank" rel="noopener noreferrer" style={{ color: '#58a6ff' }}>
                    📦 {result.npm_url}
                  </a>
                </div>
              )}
              {result.pr_url && (
                <div style={{ marginTop: 8 }}>
                  <a href={result.pr_url} target="_blank" rel="noopener noreferrer" style={{ color: '#58a6ff' }}>
                    🔀 {result.pr_url}
                  </a>
                </div>
              )}
            </div>
          )}

          {/* Validation Info */}
          {selectedSkillData && !selectedSkillData.valid && (
            <div style={{
              marginTop: 12,
              padding: 10,
              borderRadius: 6,
              background: 'rgba(248,81,73,0.06)',
              border: '1px solid rgba(248,81,73,0.15)',
              fontSize: 12,
              color: '#f85149',
            }}>
              ⚠️ 이 스킬은 아직 publish 조건을 충족하지 못했습니다. SKILL.md 파일이 있는지 확인하세요.
            </div>
          )}
        </div>
      )}

      {/* ─── Publish History ───────────────────────────────────────── */}
      <div className="glass-panel" style={{ padding: 16 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onClick={() => setHistoryExpanded(!historyExpanded)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16 }}>📋</span>
            <h3 style={{ margin: 0, fontSize: 14 }}>Publish History</h3>
            <span className="status-badge" style={{
              fontSize: 10,
              padding: '2px 8px',
              background: 'rgba(255,255,255,0.08)',
              color: 'var(--text-secondary)',
            }}>
              {history.length}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {historyExpanded ? '▼' : '▶'}
            </span>
          </div>
          {history.length > 0 && (
            <button
              className="glass-btn"
              onClick={(e) => { e.stopPropagation(); clearHistory(); }}
              style={{ padding: '4px 10px', fontSize: 11, color: '#f85149' }}
            >
              🗑️ Clear All
            </button>
          )}
        </div>

        {historyExpanded && (
          <div style={{ marginTop: 12 }}>
            {history.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '12px 0', textAlign: 'center' }}>
                아직 publish 기록이 없습니다.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {history.map(entry => (
                  <div key={entry.id}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '8px 12px',
                        borderRadius: 6,
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid rgba(255,255,255,0.06)',
                        cursor: 'pointer',
                        fontSize: 12,
                        transition: 'all 0.15s ease',
                      }}
                      onClick={() => setExpandedEntryId(expandedEntryId === entry.id ? null : entry.id)}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                    >
                      <span style={{ fontSize: 14 }}>
                        {entry.success ? '✅' : '❌'}
                      </span>
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <strong>{esc(entry.skill_name)}</strong>
                        <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                          {entry.action === 'npm_publish' ? '📦 npm' : entry.action === 'github_pr' ? '🔀 PR' : ''}
                          {entry.dry_run ? ' (dry-run)' : ''}
                        </span>
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontSize: 11, flexShrink: 0 }}>
                        {formatTime(entry.timestamp)}
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontSize: 10, marginLeft: 4 }}>
                        {expandedEntryId === entry.id ? '▲' : '▼'}
                      </span>
                    </div>

                    {/* Expanded details */}
                    {expandedEntryId === entry.id && (
                      <div style={{
                        margin: '2px 0 0 0',
                        padding: '10px 14px',
                        borderRadius: '0 0 6px 6px',
                        background: 'rgba(0,0,0,0.15)',
                        border: '1px solid rgba(255,255,255,0.06)',
                        borderTop: 'none',
                        fontSize: 12,
                        lineHeight: 1.6,
                      }}>
                        <div style={{ color: entry.success ? '#3fb950' : '#f85149', fontWeight: 600, marginBottom: 6 }}>
                          {entry.success ? '✅ Success' : '❌ Failed'}
                        </div>

                        <div style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>
                          {entry.summary}
                        </div>

                        {entry.version && (
                          <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>
                            📦 v{entry.version}
                            {entry.package_name && <span> · {esc(entry.package_name)}</span>}
                          </div>
                        )}

                        {entry.errors.length > 0 && (
                          <div style={{ marginTop: 6, color: '#f85149' }}>
                            {entry.errors.map((e, i) => <div key={i}>• {e}</div>)}
                          </div>
                        )}
                        {entry.warnings.length > 0 && (
                          <div style={{ marginTop: 4, color: '#d29922' }}>
                            {entry.warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
                          </div>
                        )}
                        {entry.npm_url && (
                          <div style={{ marginTop: 6 }}>
                            <a href={entry.npm_url} target="_blank" rel="noopener noreferrer" style={{ color: '#58a6ff' }}>
                              📦 {entry.npm_url}
                            </a>
                          </div>
                        )}
                        {entry.pr_url && (
                          <div style={{ marginTop: 4 }}>
                            <a href={entry.pr_url} target="_blank" rel="noopener noreferrer" style={{ color: '#58a6ff' }}>
                              🔀 {entry.pr_url}
                            </a>
                          </div>
                        )}

                        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                          🕐 {formatTime(entry.timestamp)}
                          {entry.dry_run && <span> · 🔄 Dry-run</span>}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PublishTab;
