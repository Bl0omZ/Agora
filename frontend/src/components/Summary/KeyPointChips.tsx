import styles from './DiscussionSummaryDashboard.module.css';

interface Props {
  points: string[];
}

export function KeyPointChips({ points }: Props) {
  if (points.length === 0) return null;
  return (
    <div className={styles.chips}>
      {points.map((p, i) => (
        <span key={i} className={styles.chip}>{p}</span>
      ))}
    </div>
  );
}
