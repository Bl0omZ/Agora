import type { DegradedReason } from '../../types';
import styles from './DiscussionSummaryDashboard.module.css';

const REASON_LABEL: Record<DegradedReason, string> = {
  json_parse_failed: 'Synthesizer JSON 解析失败',
  synthesis_truncated: '总结文本超长被截断',
};

interface Props {
  reason: DegradedReason | null;
}

export function DegradedBanner({ reason }: Props) {
  return (
    <div className={styles.degraded} role="status">
      <span className={styles.degradedIcon} aria-hidden>ⓘ</span>
      <div>
        <strong>本次自动提炼失败，已展示压缩版</strong>
        {reason && <p className={styles.degradedReason}>原因：{REASON_LABEL[reason] ?? reason}</p>}
      </div>
    </div>
  );
}
