import type { DiscussionSummary, AgentVoteOverlay } from '../../types';
import { AgentRow } from './AgentRow';
import { DegradedBanner } from './DegradedBanner';
import { DistilledConclusion } from './DistilledConclusion';
import styles from './DiscussionSummaryDashboard.module.css';

interface Props {
  summary: DiscussionSummary;
  /** 来自 voting 阶段；synthesis 阶段渲染时为空数组或 undefined。 */
  voteOverlays?: AgentVoteOverlay[];
}

export function DiscussionSummaryDashboard({ summary, voteOverlays }: Props) {
  const agentCount = summary.participants.length;
  const messageTotal = summary.participants.reduce((sum, p) => sum + p.message_count, 0);
  const overlayByName = new Map<string, AgentVoteOverlay>(
    (voteOverlays ?? []).map(o => [o.agent_name, o]),
  );

  return (
    <div className={styles.card} role="region" aria-label="讨论总结">
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.kicker}>DISCUSSION SUMMARY</span>
          <h3 className={styles.title}>讨论总结</h3>
        </div>
        {agentCount > 0 && (
          <span className={styles.headerMeta}>
            {agentCount} 位参与者 · {messageTotal} 条
          </span>
        )}
      </div>

      {summary.degraded && <DegradedBanner reason={summary.degraded_reason ?? null} />}

      {agentCount > 0 && (
        <section>
          <h4 className={styles.sectionTitle}>参与与论点</h4>
          <div className={styles.agentList} role="list">
            {summary.participants.map(p => (
              <AgentRow
                key={p.name}
                participant={p}
                voteOverlay={overlayByName.get(p.name) ?? null}
              />
            ))}
          </div>
        </section>
      )}

      {summary.distilled_conclusion && (
        <section>
          <h4 className={styles.sectionTitle}>提炼结论</h4>
          <DistilledConclusion text={summary.distilled_conclusion} />
        </section>
      )}
    </div>
  );
}
