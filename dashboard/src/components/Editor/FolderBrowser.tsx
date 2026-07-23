/**
 * FolderBrowser — Modal for browsing the system filesystem
 * ==========================================================
 * Ported from Vanilla JS folder modal. Allows navigating and
 * selecting a workspace folder.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useFileStore } from '../../stores/fileStore';
import { useUiStore } from '../../stores/uiStore';

interface BrowseItem {
  name: string;
  path: string;
  is_dir: boolean;
}

interface BrowseData {
  current: string;
  parent: string | null;
  items: BrowseItem[];
}

const FolderBrowser: React.FC = () => {
  const { folderBrowserVisible, setFolderBrowserVisible, addToast } = useUiStore();
  const { setWorkspacePath, refreshTree } = useFileStore();

  const [browseData, setBrowseData] = useState<BrowseData | null>(null);
  const [currentPath, setCurrentPath] = useState('/');
  const [loading, setLoading] = useState(false);

  const loadBrowse = useCallback(async (dir: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/fs/browse?dir=${encodeURIComponent(dir)}`);
      const data = await res.json();
      if (data.ok) {
        setBrowseData(data);
        setCurrentPath(data.current);
      }
    } catch (err) {
      console.error('Browse error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (folderBrowserVisible) {
      loadBrowse('/');
    }
  }, [folderBrowserVisible, loadBrowse]);

  const handleSelectFolder = useCallback(async () => {
    try {
      // Set workspace via API
      const res = await fetch('/api/fs/workspace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: currentPath }),
      });
      const data = await res.json();
      if (data.ok) {
        setWorkspacePath(data.workspace);
        localStorage.setItem('agk_active_project', data.workspace);
        addToast(`📂 워크스페이스 변경: ${data.workspace}`, 'success');
        refreshTree();
        setFolderBrowserVisible(false);
      } else {
        addToast(`워크스페이스 설정 실패: ${data.detail}`, 'error');
      }
    } catch (err: any) {
      addToast(`오류: ${err.message}`, 'error');
    }
  }, [currentPath, setWorkspacePath, refreshTree, setFolderBrowserVisible, addToast]);

  const handleNavigate = useCallback((dirPath: string) => {
    loadBrowse(dirPath);
  }, [loadBrowse]);

  if (!folderBrowserVisible) return null;

  return (
    <div
      className="modal-overlay"
      style={{ zIndex: 9998 }}
      onClick={() => setFolderBrowserVisible(false)}
    >
      <div
        className="modal-content glass-panel"
        style={{
          width: 520,
          maxHeight: '70vh',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--glass-border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h3 style={{ margin: 0, fontSize: 14 }}>📂 프로젝트 폴더 선택</h3>
          <button
            className="icon-btn"
            style={{ color: 'var(--text-secondary)' }}
            onClick={() => setFolderBrowserVisible(false)}
          >
            ✕
          </button>
        </div>

        {/* Current Path Display */}
        <div
          style={{
            padding: '8px 16px',
            background: 'rgba(0,0,0,0.2)',
            fontSize: 12,
            color: 'var(--text-secondary)',
            wordBreak: 'break-all',
            borderBottom: '1px solid var(--glass-border)',
          }}
        >
          {loading ? 'Loading...' : currentPath}
        </div>

        {/* Items List */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px 0',
          }}
        >
          {/* Parent directory (up button) */}
          {browseData?.parent && (
            <div
              className="browse-item"
              onClick={() => handleNavigate(browseData.parent!)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                cursor: 'pointer',
                fontSize: 13,
                color: 'var(--text-secondary)',
                borderRadius: 6,
                margin: '0 6px',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(124,106,239,0.1)';
                e.currentTarget.style.color = 'var(--text-primary)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = '';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              <span>📂</span>
              <span>.. (상위 폴더)</span>
            </div>
          )}

          {browseData?.items.map(item => (
            <div
              key={item.path}
              className="browse-item"
              onClick={() => item.is_dir && handleNavigate(item.path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                cursor: item.is_dir ? 'pointer' : 'default',
                fontSize: 13,
                color: 'var(--text-secondary)',
                borderRadius: 6,
                margin: '0 6px',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={e => {
                if (item.is_dir) {
                  e.currentTarget.style.background = 'rgba(124,106,239,0.1)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = '';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              <span>{item.is_dir ? '📁' : '📄'}</span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {item.name}
              </span>
            </div>
          ))}

          {browseData?.items.length === 0 && (
            <div
              style={{
                padding: 16,
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: 12,
              }}
            >
              빈 폴더입니다
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--glass-border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <button
            className="glass-btn small"
            onClick={() => browseData?.parent && handleNavigate(browseData.parent)}
            title="상위 폴더"
            style={{
              padding: '6px 12px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid var(--glass-border)',
              borderRadius: 6,
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: 12,
            }}
          >
            ⬆️ 상위
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="glass-btn small"
              onClick={() => setFolderBrowserVisible(false)}
              style={{
                padding: '6px 12px',
                background: 'transparent',
                border: '1px solid var(--glass-border)',
                borderRadius: 6,
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              취소
            </button>
            <button
              className="glass-btn small primary"
              onClick={handleSelectFolder}
              style={{
                padding: '6px 12px',
                background: 'var(--accent-color)',
                border: 'none',
                borderRadius: 6,
                color: '#fff',
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              이 폴더 선택
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FolderBrowser;
