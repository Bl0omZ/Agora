import styles from './Welcome.module.css';

interface WelcomeProps {
  onStart: (topic: string) => void;
}

export function Welcome({ onStart }: WelcomeProps) {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const input = form.elements.namedItem('topic') as HTMLInputElement;
    const topic = input.value.trim();
    if (topic) {
      onStart(topic);
      input.value = '';
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
          <input
            name="topic"
            type="text"
            className={styles.input}
            placeholder="输入讨论话题…"
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
