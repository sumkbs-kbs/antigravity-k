/**
 * ChatHistory — Sidebar modal showing conversation sessions
 */

import React from 'react';
import { useChatStore } from '../../stores/chatStore';

interface Props {
  visible: boolean;
  onClose: () => void;
}

const ChatHistory: React.FC<Props> = ({ visible, onClose }) => {
  const { sessions, activeSessionId, switchSession, deleteSession, createNewSession, updateSessionTitle } = useChatStore();
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editTitle, setEditTitle] = React.useState('');

  if (!visible) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content glass-panel"
        style={{ width: 400, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: 16, borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>Chat History</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="icon-btn" onClick={createNewSession} title="New Chat" aria-label="새 채팅">➕</button>
            <button className="icon-btn" onClick={onClose} title="Close" aria-label="닫기">✕</button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 0 }}>
          {sessions.length === 0 ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-secondary)' }}>
              No chat history found.
            </div>
          ) : (
            sessions.map(session => {
              const isActive = session.id === activeSessionId;
              const dateStr = new Date(session.updatedAt).toLocaleString();
              return (
                <div
                  key={session.id}
                  className={`history-item ${isActive ? 'active' : ''}`}
                  onClick={() => { switchSession(session.id); onClose(); }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); switchSession(session.id); onClose(); } }}
                  style={{ display: 'flex', alignItems: 'center', padding: '10px 12px' }}
                >
                  <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
                    {editingId === session.id ? (
                      <input
                        type="text"
                        value={editTitle}
                        autoFocus
                        style={{
                          width: '90%',
                          background: '#0d1117',
                          border: '1px solid var(--accent-color)',
                          borderRadius: 4,
                          color: '#f0f6fc',
                          fontSize: 13,
                          padding: '2px 6px',
                          outline: 'none',
                        }}
                        onChange={e => setEditTitle(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') {
                            if (editTitle.trim()) updateSessionTitle(session.id, editTitle.trim());
                            setEditingId(null);
                          } else if (e.key === 'Escape') {
                            setEditingId(null);
                          }
                        }}
                        onBlur={() => {
                          if (editTitle.trim()) updateSessionTitle(session.id, editTitle.trim());
                          setEditingId(null);
                        }}
                        onClick={e => e.stopPropagation()}
                      />
                    ) : (
                      <div className="truncate" style={{ fontSize: 13, fontWeight: 500 }}>
                        {session.title}
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      {dateStr}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 4, marginLeft: 'auto', flexShrink: 0 }}>
                    <button
                      type="button"
                      onClick={e => {
                        e.stopPropagation();
                        setEditingId(session.id);
                        setEditTitle(session.title || '새 대화');
                      }}
                      title="Rename"
                      aria-label={`${session.title} 채팅 이름 변경`}
                      style={{
                        background: 'transparent', border: 'none',
                        color: 'var(--text-muted)', fontSize: 13, padding: '4px 6px',
                        cursor: 'pointer', borderRadius: 6,
                      }}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      className="delete-session-btn"
                      onClick={e => { e.stopPropagation(); deleteSession(session.id); }}
                      title="Delete"
                      aria-label={`${session.title} 채팅 삭제`}
                      style={{
                        background: 'transparent', border: 'none',
                        color: 'var(--text-muted)', fontSize: 15, padding: '4px 6px',
                        cursor: 'pointer', borderRadius: 6,
                      }}
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatHistory;
