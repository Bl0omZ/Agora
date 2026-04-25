import { useEffect, useRef } from 'react';
import type { Message, VotingResult } from '../../types';
import { HostMessage } from './HostMessage';
import { MessageBubble } from './MessageBubble';
import { PhaseDivider } from './PhaseDivider';
import { VotingCard } from './VotingCard';
import { TypingIndicator } from './TypingIndicator';
import styles from './Timeline.module.css';

interface TimelineProps {
  messages: Message[];
  votingResult: VotingResult | null;
  thinkingAgent: string | null;
}

export function Timeline({ messages, votingResult, thinkingAgent }: TimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, votingResult, thinkingAgent]);

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
              {msg.name === 'Host' || msg.meta?.variant ? (
                <HostMessage message={msg} meta={msg.meta} />
              ) : (
                <MessageBubble message={msg} />
              )}
            </div>
          );
        })}
        {votingResult && <VotingCard result={votingResult} />}
        {thinkingAgent && <TypingIndicator agentName={thinkingAgent} />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
