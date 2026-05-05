import { useEffect, useRef, useState } from 'react';
import styles from './Welcome.module.css';

interface WelcomeProps {
  onStart: (topic: string) => void;
}

export function Welcome({ onStart }: WelcomeProps) {
  const [topic, setTopic] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 240)}px`;
  }, [topic]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmedTopic = topic.trim();
    if (trimmedTopic) {
      onStart(trimmedTopic);
      setTopic('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  };

  return (
    <div className={styles.welcome}>
      <div className={styles.content}>
        <h1 className={styles.title}>Agent Discussion</h1>
        <p className={styles.subtitle}>多智能体协作讨论平台</p>
        <p className={styles.description}>
          输入一个话题，多个 AI Agent 将从不同视角展开讨论、辩论和总结。
        </p>
        <form className={styles.form} onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            name="topic"
            className={styles.input}
            placeholder="输入讨论话题…"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          <button type="submit" className={styles.button}>
            开始讨论
          </button>
        </form>
      </div>
    </div>
  );
}