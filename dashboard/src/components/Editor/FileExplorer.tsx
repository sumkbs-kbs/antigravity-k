/**
 * FileExplorer — Explorer panel with header + file tree
 * =======================================================
 * Single component combining header buttons and file tree,
 * to be placed in .ide-explorer in the chat layout.
 * Also provides a New Folder modal.
 */

import React, { useState, useEffect, useRef } from 'react';
import FileTree from './FileTree';
import SearchPanel from './SearchPanel';
import { useFileStore } from '../../stores/fileStore';
import { useEditorStore } from '../../stores/editorStore';
import { useUiStore } from '../../stores/uiStore';

interface NewFolderModalProps {
  visible: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}

const NewFolderModal: React.FC<NewFolderModalProps> = ({ visible, onClose, onCreate }) => {
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (visible) {
      setName('');
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [visible]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    await onCreate(name.trim());
    setCreating(false);
    onClose();
  };

  if (!visible) return null;

  return (
    <div
      className="modal-overlay"
      style={{ zIndex: 9999 }}
      onClick={onClose}
    >
      <div
        className="modal-content glass-panel"
        style={{ width: 400 }}
        onClick={e => e.stopPropagation()}
      >
        <div
          style={{
            padding: 16,
            borderBottom: '1px solid var(--glass-border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h3 style={{ margin: 0, fontSize: 14 }}>📁 새 폴더</h3>
          <button className="icon-btn" onClick={onClose} style={{ color: 'var(--text-secondary)' }}>✕</button>
        </div>
        <div style={{ padding: 16 }}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
            새로 생성할 폴더 이름을 입력하세요 (워크스페이스 기준):
          </label>
          <input
            ref={inputRef}
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            placeholder="새 폴더"
            style={{
              width: '100%',
              padding: 8,
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--glass-border)',
              color: '#fff',
              borderRadius: 4,
              outline: 'none',
            }}
          />
        </div>
        <div
          style={{
            padding: 16,
            borderTop: '1px solid var(--glass-border)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 8,
          }}
        >
          <button
            className="btn"
            onClick={onClose}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              border: '1px solid var(--glass-border)',
              borderRadius: 6,
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: 12,
            }}
          >
            Cancel
          </button>
          <button
            className="btn"
            onClick={handleCreate}
            disabled={creating || !name.trim()}
            style={{
              padding: '8px 16px',
              background: creating ? 'var(--text-muted)' : 'var(--accent-color)',
              border: 'none',
              borderRadius: 6,
              color: '#fff',
              cursor: creating ? 'not-allowed' : 'pointer',
              fontSize: 12,
            }}
          >
            {creating ? '생성 중...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

const FileExplorer: React.FC = () => {
  const { refreshTree, createFolder, loadDirectory, getWorkspace } = useFileStore();
  const { openFiles, saveFile } = useEditorStore();
  const { setFolderBrowserVisible, addToast } = useUiStore();
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [savingAll, setSavingAll] = useState(false);

  // Load tree on mount
  useEffect(() => {
    const init = async () => {
      await getWorkspace();
      await refreshTree();
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Listen for global toggle-search event (Cmd+Shift+F)
  useEffect(() => {
    const handler = () => setShowSearch(s => !s);
    window.addEventListener('agk:toggle-search', handler);
    return () => window.removeEventListener('agk:toggle-search', handler);
  }, []);

  const handleRefresh = () => refreshTree();
  const handleOpenFolder = () => setFolderBrowserVisible(true);

  const handleIndexWorkspace = async () => {
    try {
      const res = await fetch('/api/workspace/ingest', { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        addToast('🧠 워크스페이스 인덱싱 시작됨', 'info');
      } else {
        addToast(`인덱싱 실패: ${data.detail}`, 'error');
      }
    } catch (err: any) {
      addToast(`오류: ${err.message}`, 'error');
    }
  };

  const handleSaveAll = async () => {
    const dirtyFiles = openFiles.filter(f => f.isDirty);
    if (dirtyFiles.length === 0) {
      addToast('저장할 변경사항이 없습니다', 'info');
      return;
    }
    setSavingAll(true);
    let successCount = 0;
    for (const file of dirtyFiles) {
      const ok = await saveFile(file.path);
      if (ok) successCount++;
    }
    setSavingAll(false);
    addToast(`💾 ${successCount}/${dirtyFiles.length} 파일 저장됨`, successCount === dirtyFiles.length ? 'success' : 'error');
  };

  const handleCreateFolder = async (name: string) => {
    const success = await createFolder(name);
    if (success) {
      addToast(`📁 폴더 생성됨: ${name}`, 'success');
      refreshTree();
    } else {
      addToast('폴더 생성 실패', 'error');
    }
  };

  const dirtyCount = openFiles.filter(f => f.isDirty).length;

  return (
    <>
      <div className="explorer-header">
        <span className="explorer-title">EXPLORER</span>          <div style={{ display: 'flex', gap: 2 }} role="toolbar" aria-label="파일 탐색기 도구">
          {/* Save All button (shows when there are dirty files) */}
          {dirtyCount > 0 && (
            <button
              className="icon-btn"
              title={`Save All (${dirtyCount} ${dirtyCount === 1 ? 'file' : 'files'})`}
              aria-label={`모두 저장 (${dirtyCount}개 파일)`}
              onClick={handleSaveAll}
              disabled={savingAll}
              style={{ fontSize: 12, padding: '4px 6px', color: savingAll ? 'var(--text-muted)' : '#10b981' }}
            >
              💾{dirtyCount > 0 && <span style={{ fontSize: 9, marginLeft: 2 }}>{dirtyCount}</span>}
            </button>
          )}
          <button
            className="icon-btn"
            title="Search in Files (Cmd+Shift+F)"
            aria-label="파일 검색"
            onClick={() => setShowSearch(s => !s)}
            style={{
              fontSize: 12,
              padding: '4px 6px',
              color: showSearch ? 'var(--accent-color)' : undefined,
              background: showSearch ? 'rgba(124,106,239,0.12)' : undefined,
            }}
          >
            🔎
          </button>
          <button
            className="icon-btn"
            title="New Folder"
            aria-label="새 폴더"
            onClick={() => setShowNewFolder(true)}
            style={{ fontSize: 12, padding: '4px 6px' }}
          >
            📁+
          </button>
          <button
            className="icon-btn"
            title="Index Workspace (Learn Folder Knowledge)"
            aria-label="워크스페이스 인덱싱"
            onClick={handleIndexWorkspace}
            style={{ fontSize: 12, padding: '4px 6px' }}
          >
            🧠
          </button>
          <button
            className="icon-btn"
            title="Open Folder"
            aria-label="폴더 열기"
            onClick={handleOpenFolder}
            style={{ fontSize: 12, padding: '4px 6px' }}
          >
            📁
          </button>
          <button
            className="icon-btn"
            title="Refresh"
            aria-label="파일 트리 새로고침"
            onClick={handleRefresh}
            style={{ fontSize: 12, padding: '4px 6px' }}
          >
            🔄
          </button>
        </div>
      </div>
      {/* Toggle search panel / file tree */}
      {showSearch ? (
        <div className="search-panel-wrapper" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <SearchPanel visible={showSearch} onClose={() => setShowSearch(false)} />
        </div>
      ) : (
        <div className="file-tree" style={{ flex: 1, overflow: 'auto' }}>
          <FileTree />
        </div>
      )}

      <NewFolderModal
        visible={showNewFolder}
        onClose={() => setShowNewFolder(false)}
        onCreate={handleCreateFolder}
      />
    </>
  );
};

export default FileExplorer;
