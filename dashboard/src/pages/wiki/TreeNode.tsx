/**
 * TreeNode — Recursive Wiki tree node
 * =====================================
 * Extracted from WikiPage.tsx. Renders folder/file nodes
 * with expand/collapse for folders.
 */

import React, { useState } from 'react';
import type { WikiTreeItem } from '../../stores/wikiStore';

interface Props {
  item: WikiTreeItem;
  depth: number;
  onSelect: (path: string) => void;
}

const TreeNode: React.FC<Props> = ({ item, depth, onSelect }) => {
  const [open, setOpen] = useState(false);

  if (item.type === 'folder') {
    return (
      <div className="wiki-tree-node">
        <div
          className="tree-item folder"
          style={{ paddingLeft: 12 + depth * 16, cursor: 'pointer' }}
          onClick={() => setOpen(!open)}
        >
          <span className="tree-icon">{open ? '📂' : '📁'}</span>
          <span className="tree-name">{item.name}</span>
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
            {(item.children || []).length}
          </span>
        </div>
        {open && item.children && (
          <div className="tree-children">
            {item.children.map((child, i) => (
              <TreeNode key={child.path || i} item={child} depth={depth + 1} onSelect={onSelect} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className="tree-item file"
      style={{ paddingLeft: 12 + depth * 16, cursor: 'pointer' }}
      onClick={() => onSelect(item.path)}
    >
      <span className="tree-icon">📄</span>
      <span className="tree-name">{item.name}</span>
    </div>
  );
};

export default TreeNode;
