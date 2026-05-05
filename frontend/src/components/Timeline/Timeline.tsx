import { useEffect, useRef } from 'react';
import type { Message, VotingResult, AgentSystemBlueprint, BlueprintExportFormat } from '../../types';
import { HostMessage } from './HostMessage';
import { MessageBubble } from './MessageBubble';
import { PhaseDivider } from './PhaseDivider';
import { VotingCard } from './VotingCard';
import { BlueprintPanel } from '../Blueprint/BlueprintPanel';
import { TypingIndicator } from './TypingIndicator';
import styles from './Timeline.module.css';

interface TimelineProps {
  messages: Message[];
  votingResult: VotingResult | null;
  blueprint: AgentSystemBlueprint | null;
  blueprintWarnings: string[];
  onExportBlueprint: (format: BlueprintExportFormat) => void;
  thinkingAgent: string | null;
}

export function Timeline({ messages, votingResult, blueprint, blueprintWarnings, onExportBlueprint, thinkingAgent }: TimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, votingResult, blueprint, thinkingAgent]);

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
