import { useMemo } from 'react';
import type { Message } from '../../types';
import { getRoleStyle } from '../../constants';
import { RoleBadge } from '../common/RoleBadge';
import { renderMarkdown } from '../../utils/markdown';
import { formatTime } from '../../utils/time';
import styles from './MessageBubble.module.css';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const role = getRoleStyle(message.name);
  const htmlContent = useMemo(() => renderMarkdown(message.content), [message.content]);

  return (
    <div className={styles.bubble}>
      <div className={styles.avatar} style={{ background: role.color }}>
        {role.initial}
      </div>
      <div className={styles.contentWrapper}>
        <div className={styles.header}>
          <span className={styles.authorName} style={{ color: role.ink }}>
            {message.name}
          </span>
          <RoleBadge name={message.name} />
          <span className={styles.timestamp}>{formatTime(message.timestamp)}</span>
        </div>
        <div
          className={`${styles.content} markdown-content`}
          dangerouslySetInnerHTML={{ __html: htmlContent }}
        />
      </div>
    </div>
  );
}
