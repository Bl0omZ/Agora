import { PHASE_LABELS } from '../../constants';

interface PhaseDividerProps {
  phase: string;
}

export function PhaseDivider({ phase }: PhaseDividerProps) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '20px 0 8px',
    }}>
      <div style={{ flex: 1, height: 1, background: 'var(--border-light)' }} />
      <span style={{
        fontFamily: 'var(--font-display)',
        fontSize: 13,
        fontWeight: 500,
        color: 'var(--ink-muted)',
        letterSpacing: '0.04em',
      }}>
        {PHASE_LABELS[phase] ?? phase}
      </span>
      <div style={{ flex: 1, height: 1, background: 'var(--border-light)' }} />
    </div>
  );
}
