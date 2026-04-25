import styles from './LeaveConfirm.module.css';

interface LeaveConfirmProps {
  topic: string;
  messageCount: number;
  onSaveAndLeave: () => void;
  onLeaveWithoutSaving: () => void;
  onCancel: () => void;
}

export function LeaveConfirm({
  topic, messageCount,
  onSaveAndLeave, onLeaveWithoutSaving, onCancel,
}: LeaveConfirmProps) {
  return (
    <div className={styles.backdrop} onClick={onCancel}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <div className={styles.icon}>?</div>
        <div className={styles.title}>当前讨论尚未保存</div>
        <div className={styles.body}>
          <div className={styles.topicLine}>「{topic || '未命名讨论'}」</div>
          <div className={styles.metaLine}>{messageCount} 条对话记录将丢失</div>
        </div>
        <div className={styles.actions}>
          <button
            className={`${styles.btn} ${styles.btnPrimary}`}
            onClick={onSaveAndLeave}
          >
            保存为报告
          </button>
          <button
            className={`${styles.btn} ${styles.btnDanger}`}
            onClick={onLeaveWithoutSaving}
          >
            直接离开
          </button>
          <button
            className={`${styles.btn} ${styles.btnGhost}`}
            onClick={onCancel}
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
