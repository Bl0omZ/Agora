import { useMemo } from 'react';
import type {
  ComplexityAnalysis,
  ComplexityLevel,
  DispatchPlan,
  HostMessageMeta,
  Message,
} from '../../types';
import { getRoleStyle } from '../../constants';
import { renderMarkdown } from '../../utils/markdown';
import { formatTime } from '../../utils/time';
import styles from './HostMessage.module.css';

const COMPLEXITY_LABEL: Record<ComplexityLevel, string> = {
  low: '复杂度 低',
  medium: '复杂度 中等',
  high: '复杂度 高',
};

const VARIANT_TAG: Record<NonNullable<HostMessageMeta['variant']>, string> = {
  normal: '',
  complexity: '复杂度判断',
  dispatch: '派发计划',
};

const EXECUTION_MODE_LABEL = {
  direct: '直接总结',
  focused: '定向派发',
  panel: '小组讨论',
} as const;

interface HostMessageProps {
  message: Message;
  /**
   * Host 消息的结构化元数据。后端通过 message.meta 下发；缺省视为 normal variant。
   * 这里允许从外部显式传入，方便 PreviewGallery 用 mock 数据预览。
   */
  meta?: HostMessageMeta;
}

/**
 * HostMessage —— Timeline 内主持人消息的统一渲染组件。
 *
 * 三种 variant 通过 meta.variant 路由：
 *   · normal     → 普通文字气泡（content 走 markdown 渲染）
 *   · complexity → 复杂度卡（chip + rationale + 可选 dimensions）
 *   · dispatch   → 派发计划卡（精炼议题 + agent 任务列表 + 可选 rationale）
 *
 * 设计原则（PRD §「Recommended Decision」）：
 *   · 三种 variant 都是同一个 message 流的一部分，回放时不依赖控制事件
 *   · meta 缺失或 variant 未知时退化为 normal，保证旧消息能正确渲染（AC8）
 *   · 复杂度/派发不允许折叠——这是议题精炼的关键产物，要让用户一眼看到
 */
export function HostMessage({ message, meta }: HostMessageProps) {
  const effectiveMeta: HostMessageMeta = meta ?? { variant: 'normal' };
  const variant = effectiveMeta.variant ?? 'normal';

  const htmlContent = useMemo(
    () => (variant === 'normal' ? renderMarkdown(message.content) : ''),
    [variant, message.content],
  );

  const role = getRoleStyle(message.name); // Host 在 ROLE_CONFIG 中已有定义
  void role; // 保留对齐意图，但 Host 头像统一用 amber，不再走 role 色

  return (
    <div className={styles.host}>
      <div className={styles.avatar}>H</div>
      <div className={styles.contentWrapper}>
        <div className={styles.header}>
          <span className={styles.authorName}>主持人</span>
          <span className={styles.badge}>主持人</span>
          {variant !== 'normal' && (
            <span className={styles.variantTag}>{VARIANT_TAG[variant]}</span>
          )}
          <span className={styles.timestamp}>{formatTime(message.timestamp)}</span>
        </div>

        {variant === 'normal' && (
          <div
            className={`${styles.normalContent} markdown-content`}
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        )}

        {variant === 'complexity' && effectiveMeta.complexity && (
          <ComplexitySubCard complexity={effectiveMeta.complexity} />
        )}

        {variant === 'dispatch' && effectiveMeta.dispatch && (
          <DispatchSubCard
            dispatch={effectiveMeta.dispatch}
            refinedTopic={effectiveMeta.refined_topic}
          />
        )}

        {/* 兜底：变种值合法但缺数据时退化展示原始 content */}
        {((variant === 'complexity' && !effectiveMeta.complexity) ||
          (variant === 'dispatch' && !effectiveMeta.dispatch)) && (
          <div className={styles.normalContent}>{message.content}</div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// 内嵌子组件：拆出来仅为可读性，不导出
// =============================================================================

function ComplexitySubCard({ complexity }: { complexity: ComplexityAnalysis }) {
  const chipClass = `${styles.complexityChip} ${styles[complexity.level]}`;
  return (
    <div className={styles.complexityCard}>
      <div className={styles.complexityHead}>
        <span className={chipClass}>
          <span className={styles.complexityDot} />
          {COMPLEXITY_LABEL[complexity.level]}
        </span>
        <span className={styles.complexityCardTitle}>主持人复杂度判断</span>
      </div>
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
  );
}

function DispatchSubCard({
  dispatch,
  refinedTopic,
}: {
  dispatch: DispatchPlan;
  refinedTopic?: string;
}) {
  return (
    <div className={styles.dispatchCard}>
      <div className={styles.dispatchHead}>
        <span className={styles.dispatchTitle}>派发计划</span>
        <span className={styles.dispatchCount}>
          {dispatch.execution_mode
            ? EXECUTION_MODE_LABEL[dispatch.execution_mode]
            : `${dispatch.tasks.length} 位 agent`}
        </span>
      </div>
      {dispatch.expected_final_output && (
        <div className={styles.dispatchMeta}>
          <span className={styles.refinedTopicLabel}>最终产出</span>
          {dispatch.expected_final_output}
        </div>
      )}
      {refinedTopic && (
        <div className={styles.refinedTopic}>
          <span className={styles.refinedTopicLabel}>精炼议题</span>
          {refinedTopic}
        </div>
      )}
      <div className={styles.dispatchList}>
        {dispatch.tasks.map((task, i) => {
          const role = getRoleStyle(task.agent_name);
          return (
            <div key={i} className={styles.dispatchTask}>
              <span className={styles.taskAvatar} style={{ background: role.color }}>
                {role.initial}
              </span>
              <span>
                <span className={styles.taskAgentName}>{role.label}</span>
                <span className={styles.taskArrow}>→</span>
                {task.sub_topic}
              </span>
            </div>
          );
        })}
      </div>
      {dispatch.rationale && (
        <p className={styles.dispatchRationale}>{dispatch.rationale}</p>
      )}
    </div>
  );
}
