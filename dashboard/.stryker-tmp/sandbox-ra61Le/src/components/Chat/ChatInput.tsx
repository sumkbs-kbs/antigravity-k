/**
 * ChatInput — Text input with image attachment support
 * Integrates with window.__chatInputRef for approval buttons
 */
// @ts-nocheck


import React, { useState, useRef, useCallback, useEffect } from 'react';

interface Props {
  onSend: (text: string, imageDataUrl?: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
  textareaRef?: (el: HTMLTextAreaElement | null) => void;
}

const ChatInput: React.FC<Props> = ({ onSend, onStop, isStreaming, disabled, textareaRef: registerRef }) => {
  const [text, setText] = useState('');
  const [imageDataUrl, setImageDataUrl] = useState<string | null>(null);
  const [isComposing, setIsComposing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Register textarea ref with parent
  useEffect(() => {
    if (registerRef && textareaRef.current) {
      registerRef(textareaRef.current);
      // Also expose globally for approval buttons
      (window as any).__chatInputRef = textareaRef;
    }
    return () => {
      if (registerRef) registerRef(null);
    };
  }, [registerRef]);

  // Auto-resize
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
    }
  }, [text]);

  const handleSend = useCallback(() => {
    if (isStreaming) {
      onStop();
      return;
    }
    const trimmed = text.trim();
    if (!trimmed && !imageDataUrl) return;
    onSend(trimmed, imageDataUrl || undefined);
    setText('');
    setImageDataUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [text, imageDataUrl, isStreaming, onSend, onStop]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (ev) => setImageDataUrl(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file?.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (ev) => setImageDataUrl(ev.target?.result as string);
      reader.readAsDataURL(file);
    }
  }, []);

  return (
    <div className="chat-input-wrapper" onDragOver={e => e.preventDefault()} onDrop={handleDrop}>
      {/* Image Preview */}
      {imageDataUrl && (
        <div
          style={{
            padding: '8px 12px', background: 'rgba(0,0,0,0.2)',
            borderTopLeftRadius: 8, borderTopRightRadius: 8,
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <div style={{ position: 'relative', display: 'inline-block' }}>
            <img src={imageDataUrl} alt="preview" style={{ maxHeight: 60, borderRadius: 4, border: '1px solid rgba(255,255,255,0.2)' }} />
            <button
              onClick={() => { setImageDataUrl(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}
              style={{
                position: 'absolute', top: -6, right: -6, background: '#ff4444', color: 'white',
                border: 'none', borderRadius: '50%', width: 18, height: 18, fontSize: 10,
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="chat-input-area" style={{ borderTopLeftRadius: imageDataUrl ? 0 : undefined, borderTopRightRadius: imageDataUrl ? 0 : undefined }}>
        <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />
        <button className="icon-btn" onClick={() => fileInputRef.current?.click()} title="이미지 첨부 (Vision)" style={{ padding: 8, fontSize: 18, opacity: 0.7, cursor: 'pointer', background: 'transparent', border: 'none' }} disabled={disabled}>
          📎
        </button>

        <textarea
          ref={textareaRef}
          id="chat-input"
          value={text}
          onChange={e => { setText(e.target.value); }}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          placeholder="명령어나 질문을 입력하세요... (이미지 Drag & Drop 가능)"
          rows={1}
          disabled={disabled}
        />

        <button className={`send-btn ${isStreaming ? 'sending' : ''}`} onClick={handleSend} disabled={disabled && !isStreaming} title={isStreaming ? '중단' : '전송'}>
          {isStreaming ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
