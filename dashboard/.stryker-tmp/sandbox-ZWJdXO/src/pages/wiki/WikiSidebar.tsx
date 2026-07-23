/**
 * WikiSidebar — Left sidebar with document tree + search
 * ========================================================
 * Extracted from WikiPage.tsx.
 */
// @ts-nocheck


import React from 'react';
import type { WikiTreeItem } from '../../stores/wikiStore';
import TreeNode from './TreeNode';

interface Props {
  vaultPath: string;
  treeData: WikiTreeItem[];
  searchQuery: string;
  searchResults: string[];
  onSearchChange: (q: string) => void;
  onSelectDoc: (path: string) => void;
  onOpenVaultModal: () => void;
  onOpenNewModal: () => void;
}

const WikiSidebar: React.FC<Props> = ({
  vaultPath, treeData, searchQuery, searchResults,
  onSearchChange, onSelectDoc, onOpenVaultModal, onOpenNewModal,
}) => {
  const renderTree = (items: WikiTreeItem[]) => {
    return items.map((item, i) => (
      <TreeNode key={item.path || i} item={item} depth={0} onSelect={onSelectDoc} />
    ));
  };

  return (
    <div className="wiki-sidebar glass-panel">
      {/* Header */}
      <div className="wiki-sidebar-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12, borderBottom: '1px solid var(--glass-border)' }}>
        <h3 style={{ fontSize: 14, margin: 0 }}>📚 Wiki</h3>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className="icon-btn" style={{ fontSize: 12, padding: '4px 8px' }} onClick={onOpenVaultModal} title="Vault 폴더 변경">📂</button>
          <button className="icon-btn" style={{ fontSize: 12, padding: '4px 8px' }} onClick={onOpenNewModal} title="새 문서 생성">+</button>
        </div>
      </div>

      {/* Vault Path */}
      <div
        id="wiki-vault-path"
        style={{ padding: '4px 12px', fontSize: 11, color: 'var(--text-muted)', background: 'rgba(0,0,0,0.15)', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer' }}
        onClick={onOpenVaultModal}
        title={`Vault: ${vaultPath}`}
      >
        📁 {vaultPath ? (vaultPath.length > 40 ? '...' + vaultPath.slice(-37) : vaultPath) : '미설정'}
      </div>

      {/* Search */}
      <div style={{ padding: '8px 12px' }}>
        <input
          className="glass-input full-width"
          placeholder="🔍 문서 검색..."
          value={searchQuery}
          onChange={e => onSearchChange(e.target.value)}
          style={{ fontSize: 12, padding: '6px 10px', width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4, outline: 'none' }}
        />
      </div>

      {/* Tree / Search Results */}
      <div id="wiki-tree" className="wiki-tree" style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
        {searchQuery && searchResults.length > 0 ? (
          searchResults.map((p, i) => (
            <div key={i} className="tree-item file" style={{ padding: '8px 16px', cursor: 'pointer' }} onClick={() => onSelectDoc(p)}>
              <span className="tree-icon">🔍</span>
              <span className="tree-name">{p}</span>
            </div>
          ))
        ) : treeData.length > 0 ? (
          renderTree(treeData)
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)', fontSize: 13 }}>
            문서가 없습니다.<br />"+" 버튼으로 첫 문서를 생성하세요.
          </div>
        )}
      </div>
    </div>
  );
};

export default WikiSidebar;
