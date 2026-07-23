/**
 * FileTreeNode — Recursive file/folder tree with expand/collapse
 * ===========================================================
 * Uses React.memo + custom comparator to prevent unnecessary re-renders
 * when sibling nodes expand/collapse or context menus open.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useFileStore } from '../../stores/fileStore';
import { useEditorStore } from '../../stores/editorStore';
import { useUiStore } from '../../stores/uiStore';
import { getFileIcon } from '../../utils/fileIcons';

interface FileTreeNodeProps {
  name: string;
  path: string;
  isDir: boolean;
  depth: number;
}

/**
 * Custom comparator: only re-render if the node's identity or depth changed.
 * Prevents ALL tree nodes from re-rendering when one node expands/collapses.
 */
function treeNodeAreEqual(prevProps: FileTreeNodeProps, nextProps: FileTreeNodeProps): boolean {
  if (prevProps.path !== nextProps.path) return false;
  if (prevProps.name !== nextProps.name) return false;
  if (prevProps.isDir !== nextProps.isDir) return false;
  if (prevProps.depth !== nextProps.depth) return false;
  return true;
}

const FileTreeNode: React.FC<FileTreeNodeProps> = React.memo(({ name, path, isDir, depth }) => {
  const { expandedPaths, toggleExpanded, loadDirectory, createFolder, createFile, renamePath, deletePath, refreshTree } = useFileStore();
  const { openFile, closeFile, saveFile } = useEditorStore();
  const { activeFilePath, openFiles } = useEditorStore();
  const { addToast } = useUiStore();
  const [children, setChildren] = useState<Array<{ name: string; path: string; is_dir: boolean }> | null>(null);
  const [loadingChildren, setLoadingChildren] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [menuPos, setMenuPos] = useState({ x: 0, y: 0 });

  // Inline editing states
  const [editingType, setEditingType] = useState<'rename' | 'newfile' | 'newfolder' | 'confirmdelete' | null>(null);
  const [editingValue, setEditingValue] = useState('');
  const editingInputRef = useRef<HTMLInputElement>(null);

  const isExpanded = expandedPaths.has(path);
  const isActive = activeFilePath === path;
  const openFileData = openFiles.find(f => f.path === path);
  const isDirty = openFileData?.isDirty === true;

  // Focus input when editing starts
  useEffect(() => {
    if (editingType && editingInputRef.current) {
      editingInputRef.current.focus();
      editingInputRef.current.select();
    }
  }, [editingType]);

  const handleClick = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDir) {
      toggleExpanded(path);
      if (!isExpanded && children === null) {
        setLoadingChildren(true);
        const items = await loadDirectory(path);
        setChildren(items);
        setLoadingChildren(false);
      }
    } else {
      try {
        const res = await fetch(`/api/fs/read?file=${encodeURIComponent(path)}`);
        const data = await res.json();
        if (data.content !== undefined) {
          openFile(path, name, data.content);
        } else {
          addToast(`파일 읽기 실패: ${data.detail || '알 수 없는 오류'}`, 'error');
        }
      } catch (err: any) {
        addToast(`파일 읽기 오류: ${err.message}`, 'error');
      }
    }
  }, [isDir, path, name, isExpanded, children, toggleExpanded, loadDirectory, openFile, addToast]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setMenuPos({ x: e.clientX, y: e.clientY });
    setShowMenu(true);
    setEditingType(null);
    setEditingValue('');
  }, []);

  const closeMenu = useCallback(() => {
    setShowMenu(false);
    setEditingType(null);
    setEditingValue('');
  }, []);

  // Menu action: start new file creation
  const startNewFile = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    const prefix = isDir ? path : path.split('/').slice(0, -1).join('/');
    setEditingValue(prefix ? `${prefix}/` : '');
    setEditingType('newfile');
    setShowMenu(false);
  }, [isDir, path]);

  // Menu action: start new folder creation
  const startNewFolder = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    const prefix = isDir ? path : path.split('/').slice(0, -1).join('/');
    setEditingValue(prefix ? `${prefix}/` : '');
    setEditingType('newfolder');
    setShowMenu(false);
  }, [isDir, path]);

  // Menu action: start rename
  const startRename = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingValue(name);
    setEditingType('rename');
    setShowMenu(false);
  }, [name]);

  // Menu action: save
  const handleSaveThis = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    closeMenu();
    if (!openFileData || !openFileData.isDirty) return;
    const ok = await saveFile(path);
    addToast(ok ? `✅ ${name} 저장됨` : `❌ ${name} 저장 실패`, ok ? 'success' : 'error');
  }, [path, name, openFileData, saveFile, addToast, closeMenu]);

  // Menu action: start delete confirmation
  const startDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingType('confirmdelete');
    setShowMenu(false);
  }, []);

  // Confirm delete
  const confirmDelete = useCallback(async () => {
    setEditingType(null);
    const success = await deletePath(path);
    if (success) {
      addToast(`🗑️ ${name} 삭제됨`, 'success');
      if (!isDir) closeFile(path);
      refreshTree();
    } else {
      addToast(`삭제 실패`, 'error');
    }
  }, [path, name, isDir, deletePath, closeFile, refreshTree, addToast]);

  // Commit inline editing
  const commitEditing = useCallback(async () => {
    const val = editingValue.trim();
    if (!val) { setEditingType(null); return; }

    const type = editingType;
    setEditingType(null);

    if (type === 'rename') {
      const result = await renamePath(path, val);
      if (result.ok) {
        addToast(`✏️ ${name} → ${val}`, 'success');
        refreshTree();
      } else {
        addToast(`이름 변경 실패: ${result.detail || '오류'}`, 'error');
      }
    } else if (type === 'newfile') {
      const ok = await createFile(val);
      if (ok) {
        addToast(`📄 새 파일: ${val.split('/').pop()}`, 'success');
        refreshTree();
      } else {
        addToast('파일 생성 실패', 'error');
      }
    } else if (type === 'newfolder') {
      const ok = await createFolder(val);
      if (ok) {
        addToast(`📁 새 폴더: ${val.split('/').pop()}`, 'success');
        refreshTree();
      } else {
        addToast('폴더 생성 실패', 'error');
      }
    }
  }, [editingValue, editingType, path, name, renamePath, createFile, createFolder, refreshTree, addToast]);

  const handleEditingKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); commitEditing(); }
    else if (e.key === 'Escape') { e.preventDefault(); setEditingType(null); }
  }, [commitEditing]);

  // Close context menu on outside click/right-click
  useEffect(() => {
    if (!showMenu) return;
    const close = () => { setShowMenu(false); setEditingType(null); };
    window.addEventListener('click', close);
    window.addEventListener('contextmenu', close);
    return () => {
      window.removeEventListener('click', close);
      window.removeEventListener('contextmenu', close);
    };
  }, [showMenu]);

  const fileIcon = isDir
    ? (isExpanded ? '📂' : '📁')
    : getFileIcon(name);

  // Check if currently editing this node
  const isEditing = editingType !== null && editingType !== 'confirmdelete';
  const showDeleteConfirm = editingType === 'confirmdelete';

  return (
    <div>
      <div
        className={`tree-node ${isActive ? 'active' : ''} ${isEditing ? 'editing' : ''}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '3px 8px',
          paddingLeft: 8 + depth * 16,
          cursor: 'pointer',
          borderRadius: 4,
          fontSize: 12,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          background: isActive ? 'rgba(124, 106, 239, 0.12)' : 'transparent',
          color: isActive ? 'var(--accent-color)' : 'var(--text-secondary)',
          transition: 'background 0.15s ease',
          userSelect: 'none',
        }}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        title={path}
        role="treeitem"
        aria-expanded={isDir ? isExpanded : undefined}
      >
        {isEditing ? (
          <input
            ref={editingInputRef}
            type="text"
            value={editingValue}
            onChange={e => setEditingValue(e.target.value)}
            onKeyDown={handleEditingKeyDown}
            onBlur={commitEditing}
            onClick={e => e.stopPropagation()}
            style={{
              flex: 1,
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid var(--accent-color)',
              borderRadius: 3,
              color: '#fff',
              fontSize: 12,
              padding: '2px 6px',
              outline: 'none',
              fontFamily: 'inherit',
              minWidth: 60,
            }}
          />
        ) : (
          <>
            <span className="tree-icon" style={{ flexShrink: 0, fontSize: 14 }}>{fileIcon}</span>
            <span className="tree-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</span>
            {isDir && loadingChildren && <span className="tree-loading-spinner" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>⟳</span>}
          </>
        )}
      </div>

      {/* Delete Confirmation Inline */}
      {showDeleteConfirm && (
        <div
          style={{
            padding: '6px 8px 6px ' + (8 + depth * 16 + 24) + 'px',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
          }}
        >
          <span style={{ color: 'var(--text-secondary)' }}>Delete "{name}"?</span>
          <button
            className="glass-btn small danger"
            onClick={e => { e.stopPropagation(); confirmDelete(); }}
            style={{ padding: '2px 8px', fontSize: 11 }}
            aria-label={`${name} 삭제 확인`}
          >
            Yes
          </button>
          <button
            className="glass-btn small"
            onClick={e => { e.stopPropagation(); setEditingType(null); }}
            style={{ padding: '2px 8px', fontSize: 11 }}
            aria-label="삭제 취소"
          >
            No
          </button>
        </div>
      )}

      {/* Context Menu */}
      {showMenu && (
        <div
          className="context-menu"
          style={{
            position: 'fixed',
            top: menuPos.y,
            left: menuPos.x,
            zIndex: 10000,
            background: 'var(--bg-secondary)',
            border: '1px solid var(--glass-border)',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            padding: '4px',
            minWidth: 160,
          }}
          onClick={e => e.stopPropagation()}
          role="menu"
          aria-label="파일 컨텍스트 메뉴"
        >
          {/* New File */}
          <div
            className="context-menu-item"
            onClick={startNewFile}
            role="menuitem"
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              fontSize: 12,
              color: 'var(--text-primary)',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'background 0.1s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(124,106,239,0.1)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span aria-hidden="true">📄</span> New File
          </div>

          {/* New Folder */}
          <div
            className="context-menu-item"
            onClick={startNewFolder}
            role="menuitem"
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              fontSize: 12,
              color: 'var(--text-primary)',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'background 0.1s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(124,106,239,0.1)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span aria-hidden="true">📁</span> New Folder
          </div>

          {/* Separator */}
          <div style={{ height: 1, background: 'var(--glass-border)', margin: '4px 8px' }} role="separator" />

          {/* Rename */}
          <div
            className="context-menu-item"
            onClick={startRename}
            role="menuitem"
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              fontSize: 12,
              color: 'var(--text-primary)',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'background 0.1s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(124,106,239,0.1)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span aria-hidden="true">✏️</span> Rename
          </div>

          {/* Save (only for dirty files) */}
          {isDirty && (
            <>
              <div style={{ height: 1, background: 'var(--glass-border)', margin: '4px 8px' }} role="separator" />
              <div
                className="context-menu-item"
                onClick={handleSaveThis}
                role="menuitem"
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  fontSize: 12,
                  color: '#10b981',
                  borderRadius: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(16,185,129,0.1)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <span aria-hidden="true">💾</span> Save
              </div>
            </>
          )}

          {/* Separator before delete */}
          <div style={{ height: 1, background: 'var(--glass-border)', margin: '4px 8px' }} role="separator" />

          {/* Delete */}
          <div
            className="context-menu-item"
            onClick={startDelete}
            role="menuitem"
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              fontSize: 12,
              color: '#ef4444',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'background 0.1s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.1)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span aria-hidden="true">🗑️</span> Delete
          </div>
        </div>
      )}

      {/* Children (only for expanded directories) */}
      {isDir && isExpanded && children && (
        <div role="group">
          {children.length === 0 ? (
            <div
              style={{
                paddingLeft: 24 + depth * 16,
                fontSize: 11,
                color: 'var(--text-muted)',
                padding: '2px 8px',
                fontStyle: 'italic',
              }}
            >
              empty
            </div>
          ) : (
            children.map(child => (
              <FileTreeNode
                key={child.path}
                name={child.name}
                path={child.path}
                isDir={child.is_dir}
                depth={depth + 1}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
});

FileTreeNode.displayName = 'FileTreeNode';

const FileTree: React.FC = () => {
  const { treeData, isLoading, refreshTree, workspacePath } = useFileStore();

  if (isLoading) {
    return <div className="tree-loading">Loading workspace...</div>;
  }

  if (treeData.length === 0) {
    return (
      <div className="tree-loading">
        <div style={{ marginBottom: 8 }}>📁 No files</div>
        <button
          className="icon-btn"
          style={{ fontSize: 11, padding: '4px 10px' }}
          onClick={refreshTree}
        >
          🔄 Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="file-tree-inner" role="tree" aria-label="File Explorer">
      {/* Workspace root node */}
      <div
        className="tree-node-root"
        style={{
          padding: '6px 8px',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--text-muted)',
          letterSpacing: '0.3px',
          borderBottom: '1px solid var(--glass-border)',
          marginBottom: 4,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <span>🏠</span>
        <span className="truncate">{(workspacePath || '/').split('/').pop() || 'workspace'}</span>
      </div>
      {treeData.map(item => (
        <FileTreeNode
          key={item.path}
          name={item.name}
          path={item.path}
          isDir={item.is_dir}
          depth={0}
        />
      ))}
    </div>
  );
};

export default FileTree;
