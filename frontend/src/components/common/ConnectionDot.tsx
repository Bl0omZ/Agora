import styles from './common.module.css';

interface ConnectionDotProps {
  status: 'connected' | 'disconnected' | 'error';
}

const LABEL_MAP: Record<string, string> = {
  connected: '已连接',
  disconnected: '连接中…',
  error: '连接失败',
};

export function ConnectionDot({ status }: ConnectionDotProps) {
  const dotClass = status === 'connected'
    ? styles.dotConnected
    : status === 'error'
      ? styles.dotError
      : styles.dotDisconnected;

  return (
    <span className={styles.connectionDot}>
      <span className={`${styles.dot} ${dotClass}`} />
      {LABEL_MAP[status] ?? status}
    </span>
  );
}
