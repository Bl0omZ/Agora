import type { AgentInfo, AgentState } from '../../types';
import { getRoleStyle } from '../../constants';
import { displayAgentName } from '../../utils/modelName';
import styles from './AgentStatusPanel.module.css';

interface AgentStatusPanelProps {
  agents: AgentInfo[];
  agentStates: Record<string, AgentState>;
  /** 仅在 preset/topic 确认后才展示 agent 列表。 */
  confirmed?: boolean;
}

function AgentStatusLabel({ state }: { state: AgentState | undefined }) {
  if (!state || state.status === 'idle') {
    return <span className={styles.statusText}>等待</span>;
  }
  if (state.status === 'thinking') {
    return (
      <span className={`${styles.statusText} ${styles.thinking}`}>
        思考中
        <span className={styles.thinkingDots}>
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
        </span>
      </span>
    );
  }
  if (state.status === 'skipped') {
    return <span className={`${styles.statusText} ${styles.skipped}`}>未参与</span>;
  }
  return <span className={styles.statusText}>已发言({state.speakCount})</span>;
}

export function AgentStatusPanel({ agents, agentStates, confirmed = true }: AgentStatusPanelProps) {
  if (agents.length === 0) return null;
  if (!confirmed) {
    return (
      <div className={styles.panel}>
        <span className={styles.waitingHint}>等待主持人分配参与者…</span>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {agents.map(agent => {
        const role = getRoleStyle(agent.name);
        const state = agentStates[agent.name];
        const isThinking = state?.status === 'thinking';
        const isModerator = agent.is_moderator === true;

        const cardClassName = [
          styles.agentCard,
          isThinking ? styles.thinking : '',
          isModerator ? styles.moderator : '',
        ]
          .filter(Boolean)
          .join(' ');

        return (
          <div key={agent.name} className={cardClassName}>
            <span className={styles.avatar} style={{ background: role.color }}>
              {role.initial}
            </span>
            <div className={styles.textCol}>
              <div className={styles.row1}>
                <span className={styles.agentName}>{displayAgentName(agent.name)}</span>
                {isModerator && <span className={styles.badge}>主持人</span>}
              </div>
              <div className={styles.row2}>
                <span className={styles.modelTag} title={agent.model}>
                  {agent.model}
                </span>
                <AgentStatusLabel state={state} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
