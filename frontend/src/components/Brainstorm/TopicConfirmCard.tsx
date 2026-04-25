import type { ComplexityLevel, TopicRefinedPayload } from '../../types';
import { getRoleStyle } from '../../constants';
import styles from './TopicConfirmCard.module.css';

interface TopicConfirmCardProps {
  payload: TopicRefinedPayload;
  /** 提交按钮是否禁用，外部正在提交时传 true。 */
  submitting?: boolean;
  /** 用户点击「开始讨论」。 */
  onConfirm: () => void;
  /** 用户点击「重新精炼」，回到 brainstorm 阶段重新走一轮提问。 */
  onRefine: () => void;
}

const COMPLEXITY_LABEL: Record<ComplexityLevel, string> = {
  low: '低',
  medium: '中等',
  high: '高',
};

const EXECUTION_MODE_LABEL = {
  direct: '直接总结',
  focused: '定向派发',
  panel: '小组讨论',
} as const;

/**
 * TopicConfirmCard —— 议题精炼完成后的确认大卡片。
 *
 * PRD 把它作为「进入 discussion 前的仪式感锚点」：
 *   · 用户始终能看到「原议题 → 精炼议题」的对照（透明性）
 *   · 用户始终能看到「主持人会怎么派发」（可控性）
 *   · 用户始终能反悔（重新精炼）或推进（开始讨论）
 *
 * 这个组件只渲染数据 + 触发回调，不持有业务状态。
 * 业务状态（提交中、重新精炼后是否回到 BrainstormPanel）由上层管理。
 */
export function TopicConfirmCard({
  payload,
  submitting = false,
  onConfirm,
  onRefine,
}: TopicConfirmCardProps) {
  const { original_topic, refined_topic, complexity, dispatch_plan } = payload;
  const complexityClassName = `${styles.complexityChip} ${styles[complexity.level]}`;

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <span className={styles.title}>议题精炼完成</span>
          <span className={styles.titleHint}>主持人已分析复杂度并准备好派发计划</span>
        </div>
        <button
          type="button"
          className={styles.refineLink}
          onClick={onRefine}
          disabled={submitting}
        >
          重新精炼 ↺
        </button>
      </div>

      {/* Topic 对照 */}
      <div className={styles.topicSection}>
        <div className={styles.topicBlock}>
          <span className={styles.topicLabel}>原议题</span>
          <div className={styles.topicOriginal}>「{original_topic}」</div>
        </div>
        <div className={styles.topicArrow}>↓ 精炼为</div>
        <div className={styles.topicBlock}>
          <span className={styles.topicLabel}>精炼议题</span>
          <div className={styles.topicRefined}>{refined_topic}</div>
        </div>
      </div>

      {/* 复杂度 */}
      <div className={styles.complexityRow}>
        <span className={styles.sectionLabel}>复杂度</span>
        <div className={styles.complexityBody}>
          <span className={complexityClassName}>
            <span className={styles.complexityDot} />
            {COMPLEXITY_LABEL[complexity.level]}
          </span>
          <p className={styles.complexityRationale}>{complexity.rationale}</p>
          {complexity.dimensions && complexity.dimensions.length > 0 && (
            <div className={styles.complexityDimensions}>
              {complexity.dimensions.map((dim, i) => (
                <span key={i} className={styles.dimensionTag}>
                  {dim}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 派发计划 */}
      <div className={styles.dispatchRow}>
        <span className={styles.sectionLabel}>派发计划</span>
        <div className={styles.dispatchBody}>
          <div className={styles.dispatchMeta}>
            <span>{dispatch_plan.execution_mode ? EXECUTION_MODE_LABEL[dispatch_plan.execution_mode] : '小组讨论'}</span>
            {dispatch_plan.expected_final_output && (
              <span>最终产出：{dispatch_plan.expected_final_output}</span>
            )}
          </div>
          {dispatch_plan.tasks.map((task, i) => {
            const role = getRoleStyle(task.agent_name);
            return (
              <div key={i} className={styles.dispatchTask}>
                <span className={styles.taskAvatar} style={{ background: role.color }}>
                  {role.initial}
                </span>
                <div className={styles.taskContent}>
                  <span className={styles.taskAgentName}>{role.label}</span>
                  <div className={styles.taskSubTopic}>{task.sub_topic}</div>
                  {task.expected_output && (
                    <span className={styles.taskExpected}>期望产出：{task.expected_output}</span>
                  )}
                </div>
              </div>
            );
          })}
          {dispatch_plan.rationale && (
            <p className={styles.dispatchRationale}>{dispatch_plan.rationale}</p>
          )}
        </div>
      </div>

      {/* CTA */}
      <div className={styles.footer}>
        <button
          type="button"
          className={styles.ctaPrimary}
          onClick={onConfirm}
          disabled={submitting}
        >
          {submitting ? '进入中…' : '开始讨论 →'}
        </button>
      </div>
    </div>
  );
}
