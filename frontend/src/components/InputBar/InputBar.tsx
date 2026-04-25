import { useState } from 'react';
import styles from './InputBar.module.css';

interface InputBarProps {
  onSend: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function InputBar({ onSend, placeholder = '输入追问内容…', disabled = false }: InputBarProps) {
  const [text, setText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setText('');
    }
  };

  return (
    <form className={styles.inputBar} onSubmit={handleSubmit}>
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={styles.input}
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
