/**
 * ChatInput — Text input with image attachment support
 * Integrates with window.__chatInputRef for approval buttons
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';

declare global {
  interface Window {
    __chatInputRef?: React.RefObject<HTMLTextAreaElement | null>;
  }
}

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
      window.__chatInputRef = textareaRef;
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
    reader.onload = (ev) => {
      const result = ev.target?.result;
      if (typeof result === 'string') setImageDataUrl(result);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file?.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const result = ev.target?.result;
        if (typeof result === 'string') setImageDataUrl(result);
      };
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
              aria-label="첨부 이미지 제거"
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

      {/* Input Area (TERMINAL-7 Prompt Design) */}
      <div className="chat-input-area" style={{ borderTopLeftRadius: imageDataUrl ? 0 : undefined, borderTopRightRadius: imageDataUrl ? 0 : undefined, alignItems: 'center' }}>
        <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />
        <span
          className="terminal-prompt-prefix"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--terminal-green)',
            paddingLeft: '4px',
            userSelect: 'none',
            whiteSpace: 'nowrap',
          }}
          aria-hidden="true"
        >
          $ ssak-ai &gt;
        </span>

        <button className="icon-btn" onClick={() => fileInputRef.current?.click()} title="이미지 첨부 (Vision)" aria-label="이미지 첨부" style={{ padding: '4px 6px', fontSize: 16, opacity: 0.6, cursor: 'pointer', background: 'transparent', border: 'none' }} disabled={disabled}>
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
          placeholder="enter instructions, --flags, or queries... (Shift+Enter for newline)"
          aria-label="메시지 입력"
          rows={1}
          disabled={disabled}
        />

        <button
          className={`btn-terminal ${isStreaming ? 'btn-stop' : ''}`}
          onClick={handleSend}
          disabled={disabled && !isStreaming}
          title={isStreaming ? '중단' : '전송'}
          aria-label={isStreaming ? '스트리밍 중단' : '메시지 전송'}
          style={{
            padding: '5px 12px',
            fontSize: '11px',
            height: '32px',
            borderColor: isStreaming ? 'var(--error-color)' : 'var(--accent-color)',
            color: isStreaming ? 'var(--error-color)' : 'var(--accent-color)',
          }}
        >
          {isStreaming ? '■ STOP' : '$ RUN ↵'}
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
