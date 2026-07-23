/**
 * VaultConfigModal — Vault folder path configuration modal
 * ==========================================================
 * Extracted from WikiPage.tsx.
 */
// @ts-nocheck


import React, { useEffect, useState } from 'react';
import { useWikiStore } from '../../stores/wikiStore';

interface Props {
  visible: boolean;
  onClose: () => void;
}

const VaultConfigModal: React.FC<Props> = ({ visible, onClose }) => {
  const { vaultPath, updateVaultConfig } = useWikiStore();
  const [path, setPath] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (visible) setPath(vaultPath); }, [visible, vaultPath]);

  if (!visible) return null;

  const handleSave = async () => {
    setSaving(true);
    await updateVaultConfig(path);
    setSaving(false);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glass-panel" style={{ width: 500 }} onClick={e => e.stopPropagation()}>
        <div style={{ padding: 16, borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between' }}>
          <h3 style={{ margin: 0, fontSize: 14 }}>📂 Vault 폴더 변경</h3>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: 16 }}>
          <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
            Wiki/Vault 문서가 저장될 폴더의 절대 경로를 입력하세요.
          </label>
          <input
            className="glass-input full-width"
            value={path}
            onChange={e => setPath(e.target.value)}
            style={{ fontSize: 13, padding: 8, width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 4 }}
          />
        </div>
        <div style={{ padding: 16, borderTop: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button
            className="glass-btn small"
            onClick={onClose}
            style={{ padding: '6px 12px', background: 'transparent', border: '1px solid var(--glass-border)', borderRadius: 4, color: 'var(--text-secondary)', cursor: 'pointer' }}
          >
            취소
          </button>
          <button
            className="glass-btn small primary"
            onClick={handleSave}
            disabled={saving}
            style={{ padding: '6px 12px', background: 'var(--accent-color)', border: 'none', borderRadius: 4, color: '#fff', cursor: 'pointer' }}
          >
            {saving ? '⏳' : '적용'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default VaultConfigModal;
