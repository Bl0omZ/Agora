import styles from './DiscussionSummaryDashboard.module.css';

interface Props {
  text: string;
}

export function DistilledConclusion({ text }: Props) {
  if (!text) return null;
  return <div className={styles.conclusion}>{text}</div>;
}
