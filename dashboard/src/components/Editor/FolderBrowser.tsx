/**
 * FolderBrowser — Visual File Explorer & Hierarchy Project Selector
 * ===================================================================
 * Explorer-style modal allowing users to browse their filesystem,
 * jump via breadcrumbs, use quick access shortcuts, and select/open
 * project directories with zero manual key-in required.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useFileStore } from '../../stores/fileStore';
import { useUiStore } from '../../stores/uiStore';
import { createAccessPinHeaders } from '../../utils/accessPinCredential';

interface BrowseItem {
  name: string;
  path: string;
  is_dir: boolean;
  is_project?: boolean;
  has_children?: boolean;
}

interface ShortcutItem {
  name: string;
  path: string;
}

interface BrowseData {
  current: string;
  parent: string | null;
  items: BrowseItem[];
  shortcuts?: ShortcutItem[];
}

interface ExistingProject {
  id: string;
  name: string;
  path: string;
}

const FolderBrowser: React.FC = () => {
  const { folderBrowserVisible, setFolderBrowserVisible, addToast } = useUiStore();
  const { setWorkspacePath, refreshTree } = useFileStore();

  const [browseData, setBrowseData] = useState<BrowseData | null>(null);
  const [currentPath, setCurrentPath] = useState('');
  const [selectedPath, setSelectedPath] = useState('');
  const [projectName, setProjectName] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [existingProjects, setExistingProjects] = useState<ExistingProject[]>([]);
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState<number>(-1);

  // Load existing registered projects for quick jumping
  useEffect(() => {
    if (!folderBrowserVisible) return;
    fetch('/api/projects', { headers: createAccessPinHeaders() })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (data?.projects && Array.isArray(data.projects)) {
          setExistingProjects(data.projects);
        }
      })
      .catch(() => {});
  }, [folderBrowserVisible]);

  const loadBrowse = useCallback(
    async (dir: string, pushHistory = true) => {
      setLoading(true);
      try {
        const query = dir ? `?dir=${encodeURIComponent(dir)}` : '';
        const res = await fetch(`/api/fs/browse${query}`, {
          headers: createAccessPinHeaders(),
        });
        if (!res.ok) throw new Error(`Browse failed (${res.status})`);
        const data = (await res.json()) as BrowseData & { ok: boolean };
        if (data.ok) {
          setBrowseData(data);
          setCurrentPath(data.current);
          setSelectedPath(data.current);
          const autoName = data.current.split(/[/\\]/).filter(Boolean).pop() || 'Project';
          setProjectName(autoName);
          setSearchFilter('');

          if (pushHistory) {
            setHistory(prev => {
              const sliced = prev.slice(0, historyIdx + 1);
              return [...sliced, data.current];
            });
            setHistoryIdx(prev => prev + 1);
          }
        }
      } catch (err) {
        console.error('Browse error:', err);
      } finally {
        setLoading(false);
      }
    },
    [historyIdx]
  );

  // Initialize when opened
  useEffect(() => {
    if (folderBrowserVisible) {
      setHistory([]);
      setHistoryIdx(-1);
      const timer = setTimeout(() => void loadBrowse('', true), 0);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [folderBrowserVisible]);

  // History Back / Forward
  const handleHistoryBack = useCallback(() => {
    if (historyIdx > 0) {
      const prevPath = history[historyIdx - 1];
      setHistoryIdx(historyIdx - 1);
      loadBrowse(prevPath, false);
    }
  }, [history, historyIdx, loadBrowse]);

  const handleHistoryForward = useCallback(() => {
    if (historyIdx < history.length - 1) {
      const nextPath = history[historyIdx + 1];
      setHistoryIdx(historyIdx + 1);
      loadBrowse(nextPath, false);
    }
  }, [history, historyIdx, loadBrowse]);

  const handleNavigate = useCallback(
    (dirPath: string) => {
      loadBrowse(dirPath, true);
    },
    [loadBrowse]
  );

  // Click on a folder row: single click selects, double click enters
  const handleRowClick = useCallback((item: BrowseItem) => {
    setSelectedPath(item.path);
    setProjectName(item.name);
  }, []);

  const handleRowDoubleClick = useCallback(
    (item: BrowseItem) => {
      if (item.is_dir) {
        handleNavigate(item.path);
      }
    },
    [handleNavigate]
  );

  // Confirm project addition and workspace switch
  const handleSelectFolder = useCallback(async () => {
    const target = selectedPath || currentPath;
    if (!target) return;
    try {
      const name = projectName.trim() || target.split(/[/\\]/).filter(Boolean).pop() || 'Project';
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: createAccessPinHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ path: target, name }),
      });
      if (!res.ok) throw new Error(`Workspace update failed (${res.status})`);
      const data = await res.json();
      if (data.ok) {
        const ws = data.workspace || target;
        setWorkspacePath(ws);
        localStorage.setItem('agk_active_project', ws);
        addToast(`📂 프로젝트 전환: ${data.project?.name || name}`, 'success');
        refreshTree();
        window.dispatchEvent(new CustomEvent('agk:projects-changed'));
        setFolderBrowserVisible(false);
      } else {
        addToast(`워크스페이스 설정 실패: ${data.detail}`, 'error');
      }
    } catch (err: unknown) {
      addToast(`오류: ${err instanceof Error ? err.message : String(err)}`, 'error');
    }
  }, [selectedPath, currentPath, projectName, setWorkspacePath, refreshTree, setFolderBrowserVisible, addToast]);

  // Breadcrumbs parsing
  const breadcrumbSegments = useMemo(() => {
    if (!currentPath) return [];
    const parts = currentPath.split('/').filter(Boolean);
    const result: { label: string; path: string }[] = [{ label: '/', path: '/' }];
    let accum = '';
    for (const part of parts) {
      accum += '/' + part;
      result.push({ label: part, path: accum });
    }
    return result;
  }, [currentPath]);

  // Filtered items
  const filteredItems = useMemo(() => {
    if (!browseData?.items) return [];
    if (!searchFilter.trim()) return browseData.items;
    const q = searchFilter.trim().toLowerCase();
    return browseData.items.filter(it => it.name.toLowerCase().includes(q));
  }, [browseData?.items, searchFilter]);

  if (!folderBrowserVisible) return null;

  return (
    <div
      className="modal-overlay"
      style={{
        zIndex: 9998,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(10px)',
      }}
      onClick={() => setFolderBrowserVisible(false)}
    >
      <div
        className="modal-content glass-panel"
        style={{
          width: 820,
          maxWidth: '94vw',
          height: '80vh',
          maxHeight: 680,
          display: 'flex',
          flexDirection: 'column',
          background: '#12151c',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 16,
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.7)',
          overflow: 'hidden',
          color: '#f0f6fc',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Top Header ─────────────────────────────────────────── */}
        <div
          style={{
            padding: '14px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: '#161b24',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 18 }}>📁</span>
            <div>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#f0f6fc' }}>
                프로젝트 폴더 탐색기
              </h3>
              <span style={{ fontSize: 11.5, color: '#8b949e' }}>
                원하는 폴더를 탐색하고 선택하면 작업공간으로 등록됩니다.
              </span>
            </div>
          </div>
          <button
            className="icon-btn"
            style={{
              color: '#8b949e',
              background: 'transparent',
              border: 'none',
              fontSize: 16,
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: 6,
            }}
            onClick={() => setFolderBrowserVisible(false)}
            aria-label="폴더 선택 대화상자 닫기"
          >
            ✕
          </button>
        </div>

        {/* ── Navigation & Breadcrumbs Bar ────────────────────────── */}
        <div
          style={{
            padding: '8px 16px',
            background: '#141720',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          {/* History Nav Controls */}
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              type="button"
              onClick={handleHistoryBack}
              disabled={historyIdx <= 0}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: historyIdx > 0 ? '#f0f6fc' : '#484f58',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 12,
                cursor: historyIdx > 0 ? 'pointer' : 'default',
              }}
              title="뒤로"
            >
              ←
            </button>
            <button
              type="button"
              onClick={handleHistoryForward}
              disabled={historyIdx >= history.length - 1}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: historyIdx < history.length - 1 ? '#f0f6fc' : '#484f58',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 12,
                cursor: historyIdx < history.length - 1 ? 'pointer' : 'default',
              }}
              title="앞으로"
            >
              →
            </button>
            <button
              type="button"
              onClick={() => browseData?.parent && handleNavigate(browseData.parent)}
              disabled={!browseData?.parent}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: browseData?.parent ? '#f0f6fc' : '#484f58',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 12,
                cursor: browseData?.parent ? 'pointer' : 'default',
              }}
              title="상위 폴더로 이동"
            >
              ⬆️ 상위
            </button>
          </div>

          {/* Breadcrumb Trail */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              overflowX: 'auto',
              padding: '3px 8px',
              background: '#0d1117',
              borderRadius: 6,
              border: '1px solid rgba(255, 255, 255, 0.08)',
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: 12,
            }}
          >
            {breadcrumbSegments.map((seg, idx) => (
              <React.Fragment key={seg.path}>
                {idx > 0 && <span style={{ color: '#484f58' }}>/</span>}
                <button
                  type="button"
                  onClick={() => handleNavigate(seg.path)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: idx === breadcrumbSegments.length - 1 ? '#58a6ff' : '#8b949e',
                    fontWeight: idx === breadcrumbSegments.length - 1 ? 600 : 400,
                    cursor: 'pointer',
                    padding: '2px 4px',
                    borderRadius: 4,
                    whiteSpace: 'nowrap',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = '#f0f6fc')}
                  onMouseLeave={e =>
                    (e.currentTarget.style.color =
                      idx === breadcrumbSegments.length - 1 ? '#58a6ff' : '#8b949e')
                  }
                >
                  {seg.label === '/' ? '💻 루트' : seg.label}
                </button>
              </React.Fragment>
            ))}
          </div>

          {/* Quick Filter */}
          <div style={{ width: 170 }}>
            <input
              type="text"
              placeholder="🔍 폴더 필터..."
              value={searchFilter}
              onChange={e => setSearchFilter(e.target.value)}
              style={{
                width: '100%',
                padding: '5px 9px',
                borderRadius: 6,
                background: '#0d1117',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#f0f6fc',
                fontSize: 12,
                outline: 'none',
              }}
            />
          </div>
        </div>

        {/* ── Split Body: Left Shortcuts & Right Directory Grid ──── */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* Left Shortcuts Panel */}
          <div
            style={{
              width: 220,
              borderRight: '1px solid rgba(255, 255, 255, 0.08)',
              background: '#0d1117',
              padding: '12px 8px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
            }}
          >
            {/* Quick Access */}
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: '#8b949e',
                  padding: '0 8px 6px',
                  letterSpacing: '0.04em',
                }}
              >
                📌 빠른 바로가기
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {browseData?.shortcuts?.map(sc => (
                  <button
                    key={sc.path}
                    type="button"
                    onClick={() => handleNavigate(sc.path)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '6px 8px',
                      borderRadius: 6,
                      border: 'none',
                      background: currentPath === sc.path ? '#1f242c' : 'transparent',
                      color: currentPath === sc.path ? '#58a6ff' : '#c9d1d9',
                      fontSize: 12,
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.12s ease',
                    }}
                    onMouseEnter={e => {
                      if (currentPath !== sc.path) e.currentTarget.style.background = '#161b22';
                    }}
                    onMouseLeave={e => {
                      if (currentPath !== sc.path) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <span>{sc.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Existing Projects */}
            {existingProjects.length > 0 && (
              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#8b949e',
                    padding: '8px 8px 6px',
                    borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                    letterSpacing: '0.04em',
                  }}
                >
                  🗂️ 등록된 프로젝트
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {existingProjects.map(p => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleNavigate(p.path)}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        padding: '6px 8px',
                        borderRadius: 6,
                        border: 'none',
                        background: currentPath === p.path ? '#1f242c' : 'transparent',
                        color: currentPath === p.path ? '#58a6ff' : '#c9d1d9',
                        fontSize: 12,
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.12s ease',
                      }}
                      onMouseEnter={e => {
                        if (currentPath !== p.path) e.currentTarget.style.background = '#161b22';
                      }}
                      onMouseLeave={e => {
                        if (currentPath !== p.path) e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        📦 {p.name}
                      </span>
                      <span style={{ fontSize: 10, color: '#8b949e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.path}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Explorer Grid / List */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              background: '#12151c',
              overflow: 'hidden',
            }}
          >
            {/* Explorer Stats Bar */}
            <div
              style={{
                padding: '8px 16px',
                borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                fontSize: 11.5,
                color: '#8b949e',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span>
                {loading
                  ? '⏳ 디렉토리 탐색 중...'
                  : `${filteredItems.length}개 항목 (${filteredItems.filter(i => i.is_project).length}개 프로젝트 감지)`}
              </span>
              <span style={{ fontSize: 11 }}>더블클릭: 폴더 진입 | 단일클릭: 프로젝트 선택</span>
            </div>

            {/* Folder List Scroll Area */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '6px 10px',
                display: 'flex',
                flexDirection: 'column',
                gap: 3,
              }}
            >
              {filteredItems.map(item => {
                const isSelected = selectedPath === item.path;
                return (
                  <div
                    key={item.path}
                    className="browse-item"
                    onClick={() => handleRowClick(item)}
                    onDoubleClick={() => handleRowDoubleClick(item)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => {
                      if (e.key === 'Enter') handleRowDoubleClick(item);
                      if (e.key === ' ') {
                        e.preventDefault();
                        handleRowClick(item);
                      }
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '7px 12px',
                      cursor: 'pointer',
                      fontSize: 13,
                      color: isSelected ? '#f0f6fc' : '#c9d1d9',
                      borderRadius: 8,
                      background: isSelected
                        ? 'rgba(124, 106, 239, 0.22)'
                        : 'rgba(255, 255, 255, 0.02)',
                      border: isSelected
                        ? '1px solid rgba(124, 106, 239, 0.45)'
                        : '1px solid transparent',
                      transition: 'all 0.12s ease',
                    }}
                  >
                    <span style={{ fontSize: 16 }}>{item.is_project ? '📦' : '📁'}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontWeight: item.is_project ? 600 : 500 }}>{item.name}</span>
                        {item.is_project && (
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 600,
                              color: '#34d399',
                              background: 'rgba(16, 185, 129, 0.15)',
                              border: '1px solid rgba(16, 185, 129, 0.3)',
                              padding: '1px 6px',
                              borderRadius: 10,
                            }}
                          >
                            Git / 프로젝트
                          </span>
                        )}
                      </div>
                      <span
                        style={{
                          fontSize: 10.5,
                          color: '#8b949e',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          display: 'block',
                        }}
                      >
                        {item.path}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={e => {
                        e.stopPropagation();
                        handleNavigate(item.path);
                      }}
                      style={{
                        background: 'rgba(255, 255, 255, 0.06)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        color: '#8b949e',
                        padding: '3px 8px',
                        borderRadius: 5,
                        fontSize: 11,
                        cursor: 'pointer',
                      }}
                      title="하위 폴더 열기"
                    >
                      진입 →
                    </button>
                  </div>
                );
              })}

              {!loading && filteredItems.length === 0 && (
                <div
                  style={{
                    padding: 48,
                    textAlign: 'center',
                    color: '#8b949e',
                    fontSize: 13,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <span style={{ fontSize: 28 }}>📂</span>
                  <span>하위 폴더가 없습니다.</span>
                  <span style={{ fontSize: 11.5, color: '#6e7681' }}>
                    현재 폴더를 프로젝트로 선택하려면 하단의 버튼을 누르세요.
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Footer: Selection & Action ─────────────────────────── */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            background: '#161b24',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          {/* Selected Path & Name inputs */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: '#8b949e', flexShrink: 0 }}>선택된 경로:</span>
              <span
                style={{
                  fontSize: 11.5,
                  fontFamily: 'var(--font-mono, monospace)',
                  color: '#58a6ff',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title={selectedPath || currentPath}
              >
                {selectedPath || currentPath}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: '#8b949e', flexShrink: 0 }}>프로젝트 이름:</span>
              <input
                type="text"
                value={projectName}
                onChange={e => setProjectName(e.target.value)}
                placeholder="프로젝트 이름 입력"
                style={{
                  flex: 1,
                  maxWidth: 240,
                  padding: '3px 8px',
                  borderRadius: 5,
                  background: '#0d1117',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f0f6fc',
                  fontSize: 11.5,
                  outline: 'none',
                }}
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            <button
              className="glass-btn small"
              onClick={() => setFolderBrowserVisible(false)}
              style={{
                padding: '7px 14px',
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 8,
                color: '#c9d1d9',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 500,
              }}
            >
              취소
            </button>
            <button
              className="glass-btn small primary"
              onClick={handleSelectFolder}
              disabled={loading || !(selectedPath || currentPath)}
              style={{
                padding: '7px 18px',
                background: 'linear-gradient(135deg, #7c6aef 0%, #6246ea 100%)',
                border: 'none',
                borderRadius: 8,
                color: '#fff',
                cursor: 'pointer',
                fontSize: 12.5,
                fontWeight: 600,
                boxShadow: '0 4px 14px rgba(124, 106, 239, 0.4)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>🚀 이 폴더를 프로젝트로 열기</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FolderBrowser;
