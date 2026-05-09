import { useEffect, useRef } from 'react';
import type { Message, VotingResult, AgentSystemBlueprint, BlueprintExportFormat, DiscussionSummary, AgentVoteOverlay } from '../../types';
import { HostMessage } from './HostMessage';
import { MessageBubble } from './MessageBubble';
import { PhaseDivider } from './PhaseDivider';
import { VotingCard } from './VotingCard';
import { BlueprintPanel } from '../Blueprint/BlueprintPanel';
import { DiscussionSummaryDashboard } from '../Summary/DiscussionSummaryDashboard';
import { TypingIndicator } from './TypingIndicator';
import styles from './Timeline.module.css';

interface TimelineProps {
  messages: Message[];
  votingResult: VotingResult | null;
  blueprint: AgentSystemBlueprint | null;
  blueprintWarnings: string[];
  onExportBlueprint: (format: BlueprintExportFormat) => void;
  thinkingAgent: string | null;
  discussionSummary: DiscussionSummary | null;
}

export function Timeline({ messages, votingResult, blueprint, blueprintWarnings, onExportBlueprint, thinkingAgent, discussionSummary }: TimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  const STANCE_MAP: Record<string, AgentVoteOverlay['stance']> = {
    support: 'support', oppose: 'oppose', neutral: 'neutral',
    赞成: 'support', 反对: 'oppose', 中立: 'neutral',
    timeout: 'timeout', error: 'error',
    超时: 'timeout', 异常: 'error',
  };

  const voteOverlays: AgentVoteOverlay[] = votingResult?.votes?.map(v => ({
    agent_name: v.agent_name,
    stance: STANCE_MAP[v.stance] ?? 'neutral',
    confidence: v.confidence ?? 0,
    source: v.source === 'timeout' ? 'timeout'
      : v.source === 'error' ? 'error'
      : 'valid',
    reason: v.reason ?? '',
  })) ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, votingResult, blueprint, thinkingAgent, discussionSummary]);

  let lastPhase = '';

  return (
    <div className={styles.timeline}>
      <div className={styles.inner}>
        {messages.map((msg) => {
          const showDivider = msg.phase !== lastPhase;
          lastPhase = msg.phase;
          return (
            <div key={msg.id}>
              {showDivider && <PhaseDivider phase={msg.phase} />}
              {msg.name === 'Host' || msg.meta?.variant !== undefined ? (
                <HostMessage message={msg} meta={msg.meta} />
              ) : (
                <MessageBubble message={msg} />
              )}
            </div>
          );
        })}
        {discussionSummary && (
          <DiscussionSummaryDashboard
            summary={discussionSummary}
            voteOverlays={votingResult ? voteOverlays : undefined}
          />
        )}
        {votingResult && <VotingCard result={votingResult} />}
        {blueprint && (
          <BlueprintPanel
            blueprint={blueprint}
            warnings={blueprintWarnings}
            onExport={onExportBlueprint}
          />
        )}
        {thinkingAgent && <TypingIndicator agentName={thinkingAgent} />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
