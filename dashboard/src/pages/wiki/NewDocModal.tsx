/**
 * NewDocModal — New Wiki document creation modal
 * ================================================
 * Extracted from WikiPage.tsx.
 */

import React, { useState } from 'react';
import { useWikiStore } from '../../stores/wikiStore';

interface Props {
  visible: boolean;
  onClose: () => void;
}

const NewDocModal: React.FC<Props> = ({ visible, onClose }) => {
  const { createDocument } = useWikiStore();
  const [path, setPath] = useState('');
  const [title, setTitle] = useState('');
  const [tags, setTags] = useState('');
  const [saving, setSaving] = useState(false);

  if (!visible) return null;

  const handleCreate = async () => {
    if (!path || !path.endsWith('.md')) return;
    setSaving(true);
    const tagArr = tags.split(',').map(t => t.trim()).filter(Boolean);
    await createDocument(path, title || path.split('/').pop()?.replace('.md', '') || 'untitled', tagArr);
    setSaving(false);
    setPath(''); setTitle(''); setTags('');
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glass-panel" style={{ width: 440 }} onClick={e => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between' }}>
          <h3 style={{ margin: 0, fontSize: 14 }}>📝 새 문서 생성</h3>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>파일 경로 (vault 기준)</label>
            <input className="glass-input" value={path} onChange={e => setPath(e.target.value)} placeholder="예: notes/my-note.md"
              style={{ width: '100%', padding: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>제목</label>
            <input className="glass-input" value={title} onChange={e => setTitle(e.target.value)} placeholder="문서 제목"
              style={{ width: '100%', padding: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>태그 (쉼표로 구분)</label>
            <input className="glass-input" value={tags} onChange={e => setTags(e.target.value)} placeholder="architecture, notes"
              style={{ width: '100%', padding: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }} />
          </div>
        </div>
        <div style={{ padding: 16, borderTop: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onClose} style={{ padding: '6px 12px', background: 'transparent', border: '1px solid var(--glass-border)', borderRadius: 4, color: 'var(--text-secondary)', cursor: 'pointer' }}>취소</button>
          <button onClick={handleCreate} disabled={saving || !path || !path.endsWith('.md')}
            style={{ padding: '6px 12px', background: 'var(--accent-color)', border: 'none', borderRadius: 4, color: '#fff', cursor: 'pointer' }}>
            {saving ? '⏳' : '생성'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default NewDocModal;
