import type { BrainstormFailureKind, BrainstormFailureState } from '../../types';
import styles from './BrainstormStates.module.css';

// =============================================================================
// 1. BrainstormNotice —— 不打断主流程的信息条
// =============================================================================

interface BrainstormNoticeProps {
  state: BrainstormFailureState;
  /** 用户点关闭 X，可选；不传则不渲染关闭按钮。 */
  onDismiss?: () => void;
}

const NOTICE_PRESET: Record<
  BrainstormFailureKind,
  { tone: 'info' | 'warn' | 'success'; icon: string; title: string; defaultText: string }
> = {
  parse_failed: {
    tone: 'warn',
    icon: '!',
    title: '主持人解析失败',
    defaultText: '已用原议题进入讨论，不影响讨论进行。',
  },
  skipped: {
    tone: 'info',
    icon: 'i',
    title: '已跳过澄清',
    defaultText: '议题未经主持人精炼，直接进入讨论。',
  },
  timeout: {
    tone: 'warn',
    icon: '!',
    title: '议题精炼超时',
    defaultText: '5 分钟内未收到回答，已自动跳过澄清进入讨论。',
  },
  reconnected: {
    tone: 'success',
    icon: '✓',
    title: '已恢复未完成的议题精炼',
    defaultText: '从断开点继续，主持人之前的问题保留可见。',
  },
};

/**
 * BrainstormNotice —— Brainstorm 阶段的兜底信息条。
 *
 * 不打断主流程：用户依然能看到 Timeline 上下文，只是顶部多一条说明。
 * 与 PRD「失败安全原则」对齐：哪怕 LLM 解析炸了，讨论照常进行。
 */
export function BrainstormNotice({ state, onDismiss }: BrainstormNoticeProps) {
  const preset = NOTICE_PRESET[state.kind];
  const text = state.message ?? preset.defaultText;

  return (
    <div className={`${styles.notice} ${styles[preset.tone]}`}>
      <span className={styles.noticeIcon}>{preset.icon}</span>
      <div className={styles.noticeBody}>
        <span className={styles.noticeTitle}>{preset.title}</span>
        <span className={styles.noticeText}>{text}</span>
      </div>
      {onDismiss && (
        <button type="button" className={styles.noticeAction} onClick={onDismiss}>
          知道了
        </button>
      )}
    </div>
  );
}

// =============================================================================
// 2. BrainstormSkipConfirm —— 跳过澄清的二次确认 modal
// =============================================================================

interface BrainstormSkipConfirmProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * 跳过澄清确认弹窗。
 *
 * 设计取舍：
 *   · 跳过本身是合法操作（PRD「用户始终可逃逸」），所以确认按钮不阻止；
 *   · 但用红色变种提醒用户「跳过后议题不被精炼」，避免误触。
 *   · 如果用户已经答了几轮，建议在 onConfirm 之前也保留之前的回答（由上层处理）。
 */
export function BrainstormSkipConfirm({
  open,
  onCancel,
  onConfirm,
}: BrainstormSkipConfirmProps) {
  if (!open) return null;
  return (
    <div className={styles.modalBackdrop} onClick={onCancel}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3 className={styles.modalTitle}>跳过议题精炼？</h3>
        <p className={styles.modalBody}>
          跳过后议题将<strong>不被主持人精炼</strong>，直接以原议题进入讨论。
          已经回答的内容会保留，但不会再触发新的提问。
        </p>
        <div className={styles.modalActions}>
          <button type="button" className={styles.modalCancel} onClick={onCancel}>
            继续精炼
          </button>
          <button
            type="button"
            className={`${styles.modalConfirm} ${styles.danger}`}
            onClick={onConfirm}
          >
            跳过，直接讨论
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// 3. BrainstormLoadingPlaceholder —— 等待主持人下一个问题
// =============================================================================

interface BrainstormLoadingProps {
  /** 自定义文案；不传时显示「主持人正在思考下一个问题…」。 */
  message?: string;
}

/**
 * 议题精炼的中间等待态。
 *
 * 触发场景：用户提交了 moderator_answer 之后、下一个 moderator_question 到达之前。
 * 这段空窗如果没有占位会让人怀疑「卡了吗」，所以给一个低饱和度 dashed border 占位。
 */
export function BrainstormLoadingPlaceholder({
  message = '主持人正在思考下一个问题…',
}: BrainstormLoadingProps) {
  return (
    <div className={styles.loading}>
      <span>{message}</span>
      <span className={styles.loadingDots}>
        <span className={styles.loadingDot} />
        <span className={styles.loadingDot} />
        <span className={styles.loadingDot} />
      </span>
    </div>
  );
}
