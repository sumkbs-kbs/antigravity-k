/**
 * ContentPanel — Main wiki content area
 * =======================================
 * Extracted from WikiPage.tsx. Shows breadcrumb, action buttons,
 * metadata, markdown viewer (read-only) or textarea editor.
 */

import React from 'react';
import type { WikiDocument } from '../../stores/wikiStore';
import { renderMarkdown } from './MarkdownRenderer';

interface Props {
  currentDoc: WikiDocument | null;
  isEditing: boolean;
  editContent: string;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onChatRef: () => void;
  onEditContentChange: (content: string) => void;
}

const ContentPanel: React.FC<Props> = ({
  currentDoc, isEditing, editContent,
  onEdit, onSave, onCancel, onChatRef, onEditContentChange,
}) => {
  // Render metadata block
  const metaHtml = currentDoc && Object.keys(currentDoc.metadata).length > 0 ? (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid var(--glass-border)' }}>
      {currentDoc.metadata.title && (
        <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-secondary)' }}>
          📝 {currentDoc.metadata.title as string}
        </span>
      )}
      {currentDoc.metadata.date && (
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {currentDoc.metadata.date as string}
        </span>
      )}
      {(currentDoc.metadata.tags as string[] | undefined)?.length ? (
        <div style={{ display: 'flex', gap: 4, marginBottom: 12, width: '100%' }}>
          {(currentDoc.metadata.tags as string[]).map((t, i) => (
            <span key={i} className="status-badge" style={{ background: 'rgba(124,106,239,0.1)', color: 'var(--accent-color)', fontSize: 11, padding: '2px 8px', borderRadius: 4 }}>
              #{t}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  ) : null;

  return (
    <div className="wiki-content glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-primary)' }}>
      {/* Header with breadcrumb + actions */}
      <div className="wiki-content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12, borderBottom: '1px solid var(--glass-border)' }}>
        <div id="wiki-breadcrumb" className="breadcrumb" style={{ fontSize: 12 }}>
          {currentDoc ? currentDoc.path : '문서를 선택하세요'}
        </div>
        <div className="wiki-actions" style={{ display: 'flex', gap: 6 }}>
          {currentDoc && !isEditing && (
            <>
              <button className="glass-btn small" onClick={onChatRef}>💬 채팅 참조</button>
              <button className="glass-btn small" onClick={onEdit}>✏️ 편집</button>
            </>
          )}
          {isEditing && (
            <>
              <button className="glass-btn small primary" onClick={onSave}>💾 저장</button>
              <button className="glass-btn small" onClick={onCancel}>취소</button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div id="wiki-body" className="wiki-markdown-body" style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
        {!currentDoc ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, color: 'var(--text-muted)' }}>
            <span style={{ fontSize: 48, opacity: 0.3 }}>📚</span>
            <p style={{ fontSize: 14 }}>왼쪽 트리에서 문서를 선택하거나 새 문서를 생성하세요.</p>
          </div>
        ) : isEditing ? (
          <textarea
            id="wiki-editor"
            value={editContent}
            onChange={e => onEditContentChange(e.target.value)}
            style={{
              width: '100%', height: '100%', minHeight: 400,
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)',
              color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
              padding: 16, borderRadius: 8, resize: 'none', outline: 'none', lineHeight: 1.7,
              boxSizing: 'border-box',
            }}
          />
        ) : (
          <>
            {metaHtml}
            <div dangerouslySetInnerHTML={{ __html: renderMarkdown(currentDoc.content) }} />
          </>
        )}
      </div>
    </div>
  );
};

export default ContentPanel;
