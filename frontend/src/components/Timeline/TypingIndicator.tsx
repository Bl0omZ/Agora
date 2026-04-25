import { getRoleStyle } from '../../constants';

interface TypingIndicatorProps {
  agentName: string;
}

export function TypingIndicator({ agentName }: TypingIndicatorProps) {
  const role = getRoleStyle(agentName);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '12px 0',
      animation: 'fadeInUp 0.3s ease-out both',
    }}>
      <div style={{
        width: 32,
        height: 32,
        borderRadius: 4,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 14,
        fontWeight: 600,
        fontFamily: 'var(--font-mono)',
        color: 'var(--ink-inverse)',
        background: role.color,
      }}>
        {role.initial}
      </div>
      <span style={{
        fontSize: 13,
        color: 'var(--ink-muted)',
        fontStyle: 'italic',
      }}>
        {role.label} 正在思考
        <span style={{ display: 'inline-flex', gap: 2, marginLeft: 4 }}>
          {[0, 1, 2].map(i => (
            <span
              key={i}
              style={{
                width: 4,
                height: 4,
                borderRadius: '50%',
                background: 'var(--accent)',
                animation: `pulse 1.4s infinite ${i * 0.2}s`,
              }}
            />
          ))}
        </span>
      </span>
    </div>
  );
}
