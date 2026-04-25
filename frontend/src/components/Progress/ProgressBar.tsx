import type { DiscussionPhase, RoundProgress } from '../../types';
import { PHASE_ORDER, PHASE_LABELS } from '../../constants';
import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  currentPhase: DiscussionPhase;
  roundProgress: RoundProgress | null;
}

export function ProgressBar({ currentPhase, roundProgress }: ProgressBarProps) {
  const currentIndex = currentPhase === 'done'
    ? PHASE_ORDER.length
    : PHASE_ORDER.indexOf(currentPhase);

  return (
    <div className={styles.progressBar}>
      {PHASE_ORDER.map((phase, index) => {
        const isCompleted = index < currentIndex;
        const isActive = index === currentIndex && currentPhase !== 'done' && currentPhase !== 'idle';
        const dotClass = [
          styles.stepDot,
          isCompleted ? styles.completed : '',
          isActive ? styles.active : '',
        ].filter(Boolean).join(' ');
        const labelClass = [
          styles.stepLabel,
          isCompleted ? styles.completed : '',
          isActive ? styles.active : '',
        ].filter(Boolean).join(' ');

        return (
          <div className={styles.step} key={phase}>
            <span className={dotClass} />
            <span className={labelClass}>
              {PHASE_LABELS[phase]}
              {isActive && phase === 'discussion' && roundProgress && (
                <span className={styles.roundCounter}>
                  {roundProgress.current}/{roundProgress.total}
                </span>
              )}
            </span>
            {index < PHASE_ORDER.length - 1 && (
              <span className={`${styles.stepConnector} ${isCompleted ? styles.completed : ''}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
