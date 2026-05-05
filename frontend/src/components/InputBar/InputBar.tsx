import { useState, useRef, useEffect } from 'react';
import styles from './InputBar.module.css';

interface InputBarProps {
  onSend: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function InputBar({ onSend, placeholder = '输入追问内容…', disabled = false }: InputBarProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea on content change
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, [text]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setText('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter to submit, Shift+Enter for newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className={styles.inputBar} onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className={styles.input}
        rows={1}
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className={styles.sendButton}
      >
        发送
      </button>
    </form>
  );
}