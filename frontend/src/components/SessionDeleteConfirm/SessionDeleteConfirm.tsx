import type { SessionIndexEntry } from '../../types';
import styles from './SessionDeleteConfirm.module.css';

interface SessionDeleteConfirmProps {
  session: SessionIndexEntry;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function SessionDeleteConfirm({
  session, deleting, onConfirm, onCancel,
}: SessionDeleteConfirmProps) {
  return (
    <div className={styles.backdrop} onClick={deleting ? undefined : onCancel}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <div className={styles.icon}>!</div>
        <div className={styles.title}>删除这个会话？</div>
        <div className={styles.body}>
          <div className={styles.topicLine}>「{session.topic || '未命名讨论'}」</div>
          <div className={styles.metaLine}>
            {session.messageCount} 条消息会从历史会话中移除
          </div>
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            className={`${styles.btn} ${styles.btnDanger}`}
            onClick={onConfirm}
            disabled={deleting}
          >
            {deleting ? '正在删除…' : '确认删除'}
          </button>
          <button
            type="button"
            className={`${styles.btn} ${styles.btnGhost}`}
            onClick={onCancel}
            disabled={deleting}
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
