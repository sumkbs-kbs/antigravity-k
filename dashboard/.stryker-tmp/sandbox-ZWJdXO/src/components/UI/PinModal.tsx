/**
 * PinModal — PIN authentication modal for secure access
 */
// @ts-nocheck


import React, { useState, useRef, useEffect } from 'react';
import { useUiStore } from '../../stores/uiStore';

const PinModal: React.FC = () => {
  const visible = useUiStore(state => state.pinModalVisible);
  const setVisible = useUiStore(state => state.setPinModalVisible);
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (visible && inputRef.current) {
      inputRef.current.focus();
    }
  }, [visible]);

  const handleSubmit = async () => {
    const trimmedPin = pin.trim();
    if (!trimmedPin) return;

    localStorage.setItem('ag_access_pin', trimmedPin);

    const isHttps = window.location.protocol === 'https:';
    document.cookie = `ag_access_pin=${trimmedPin}; path=/; max-age=31536000; SameSite=Strict${isHttps ? '; Secure' : ''}`;

    try {
      const res = await fetch('/api/session/info', {
        headers: { 'X-Access-Pin': trimmedPin },
      });
      if (res.ok) {
        setVisible(false);
        window.location.reload();
      } else {
        setError('PIN 번호가 올바르지 않습니다.');
      }
    } catch {
      setError('PIN 번호가 올바르지 않습니다.');
    }
  };

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
        background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)',
        zIndex: 99999, display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        className="glass-panel"
        style={{ padding: 32, borderRadius: 16, textAlign: 'center', maxWidth: 300, width: '90%' }}
      >
        <h2 style={{ marginTop: 0 }}>🔒 시스템 잠금</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: 13 }}>
          외부 접속 보안을 위해 PIN 번호를 입력하세요.
        </p>
        <input
          ref={inputRef}
          type="password"
          value={pin}
          onChange={e => { setPin(e.target.value); setError(''); }}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          placeholder="PIN 입력"
          style={{
            width: '100%', padding: 12, borderRadius: 8, border: '1px solid var(--glass-border)',
            background: 'rgba(0,0,0,0.5)', color: '#fff', textAlign: 'center',
            fontSize: 20, letterSpacing: 4, boxSizing: 'border-box', marginBottom: 16,
          }}
          autoFocus
          aria-label="PIN 번호"
        />
        <button
          onClick={handleSubmit}
          className="glow-btn"
          style={{ width: '100%', padding: 12, borderRadius: 8, fontSize: 15, fontWeight: 'bold' }}
        >
          잠금 해제
        </button>
        {error && (
          <p style={{ color: '#ff6b6b', marginTop: 12, fontSize: 12 }} role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
};

export default PinModal;
