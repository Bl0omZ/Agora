import type { AgentParticipant, AgentVoteOverlay } from '../../types';
import { displayModelName } from '../../utils/modelName';
import { KeyPointChips } from './KeyPointChips';
import styles from './DiscussionSummaryDashboard.module.css';

const STANCE_LABEL: Record<AgentVoteOverlay['stance'], string> = {
  support: '赞成',
  oppose: '反对',
  neutral: '中立',
  timeout: '超时',
  error: '异常',
};

const STANCE_CLASS: Record<AgentVoteOverlay['stance'], string> = {
  support: styles.stanceSupport,
  oppose: styles.stanceOppose,
  neutral: styles.stanceNeutral,
  timeout: styles.stanceTimeout,
  error: styles.stanceError,
};

function avatarLetter(name: string): string {
  if (!name) return '?';
  const first = name.trim()[0];
  return first ? first.toUpperCase() : '?';
}

interface Props {
  participant: AgentParticipant;
  /** voting 阶段后注入；synthesis 阶段为 null。 */
  voteOverlay?: AgentVoteOverlay | null;
}

export function AgentRow({ participant, voteOverlay }: Props) {
  const avatarClass = `${styles.avatar} ${participant.is_moderator ? styles.avatarModerator : ''}`;
  return (
    <div
      className={styles.agentRow}
      data-agent={participant.name}
      role="listitem"
    >
      <div className={avatarClass} aria-hidden>
        {avatarLetter(participant.name)}
      </div>

      <div className={styles.agentBody}>
        <div className={styles.agentHeadRow}>
          <span className={styles.agentName}>{participant.name}</span>
          <span className={styles.agentRole}>{participant.role}</span>
          <div className={styles.agentHeadRight}>
            <span className={styles.modelTag} title={participant.model}>
              {displayModelName(participant.model)}
            </span>
            <span className={styles.messageCount}>{participant.message_count} 条</span>
          </div>
        </div>

        <KeyPointChips points={participant.key_points} />

        {voteOverlay && (
          <div className={styles.stanceRow}>
            <span
              className={`${styles.stance} ${STANCE_CLASS[voteOverlay.stance]}`}
              title={voteOverlay.reason}
            >
              {STANCE_LABEL[voteOverlay.stance]}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
