import type { VotingResult } from '../../types';
import styles from './VotingCard.module.css';

interface VotingCardProps {
  result: VotingResult;
}

function getStanceClass(stance: string): string {
  if (stance.includes('赞成')) return styles.stanceApprove;
  if (stance.includes('反对')) return styles.stanceOppose;
  return styles.stanceNeutral;
}

function getConclusionTone(conclusion: string): string {
  if (conclusion.includes('多数赞成')) return styles.conclusionApprove;
  if (conclusion.includes('多数反对')) return styles.conclusionOppose;
  return styles.conclusionNeutral;
}

export function VotingCard({ result }: VotingCardProps) {
  const counts = result.votes.reduce(
    (acc, v) => {
      if (v.stance.includes('赞成')) acc.approve += 1;
      else if (v.stance.includes('反对')) acc.oppose += 1;
      else acc.neutral += 1;
      return acc;
    },
    { approve: 0, oppose: 0, neutral: 0 },
  );

  return (
    <div className={styles.votingCard}>
      <div className={styles.votingHeader}>
        <span className={styles.votingTitle}>方案评审</span>
        <span className={styles.tally}>
          <span className={styles.tallyApprove}>赞成 {counts.approve}</span>
          <span className={styles.tallySep}>·</span>
          <span className={styles.tallyOppose}>反对 {counts.oppose}</span>
          <span className={styles.tallySep}>·</span>
          <span className={styles.tallyNeutral}>中立 {counts.neutral}</span>
        </span>
      </div>

      <div className={styles.voteList}>
        {result.votes.map((vote) => (
          <div key={vote.agent_name} className={styles.voteItem}>
            <div className={styles.voteHead}>
              <span className={styles.voteName}>{vote.agent_name}</span>
              <span className={`${styles.voteStance} ${getStanceClass(vote.stance)}`}>
                {vote.stance}
              </span>
              <span className={styles.confidence} title="置信度">
                置信 {(vote.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className={styles.voteReason}>{vote.reason}</div>
          </div>
        ))}
      </div>

      <div className={`${styles.conclusion} ${getConclusionTone(result.conclusion)}`}>
        <span className={styles.conclusionIcon}>✓</span>
        <span className={styles.conclusionLabel}>评审结论</span>
        <span className={styles.conclusionText}>{result.conclusion}</span>
      </div>
    </div>
  );
}
