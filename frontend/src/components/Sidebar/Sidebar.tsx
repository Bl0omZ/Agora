import { useState } from 'react';
import type { SessionIndexEntry, ReportEntry } from '../../types';
import { formatRelativeTime } from '../../utils/time';
import styles from './Sidebar.module.css';

interface SidebarProps {
  sessions: SessionIndexEntry[];
  currentSessionId: string | null;
  reports: ReportEntry[];
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onNewSession: () => void;
  onSelectReport: (report: ReportEntry) => void;
}

type TabKey = 'sessions' | 'reports';

export function Sidebar({
  sessions, currentSessionId, reports,
  onSelectSession, onDeleteSession, onNewSession, onSelectReport,
}: SidebarProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('sessions');

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <div className={styles.logo}>Agora</div>
        <div className={styles.subtitle}>多智能体协作讨论平台</div>
      </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'sessions' ? styles.active : ''}`}
          onClick={() => setActiveTab('sessions')}
        >
          会话
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'reports' ? styles.active : ''}`}
          onClick={() => setActiveTab('reports')}
        >
          报告
        </button>
      </div>

      {activeTab === 'sessions' ? (
        <>
          <button className={styles.newButton} onClick={onNewSession}>
            + 新建讨论
          </button>
          <div className={styles.listContainer}>
            {sessions.length === 0 ? (
              <div className={styles.emptyState}>暂无历史会话</div>
            ) : (
              sessions.map(session => (
                <div
                  key={session.id}
                  className={`${styles.sessionItem} ${session.id === currentSessionId ? styles.active : ''}`}
                  onClick={() => onSelectSession(session.id)}
                >
                  <span className={styles.sessionTopic}>{session.topic}</span>
                  <span className={styles.sessionMeta}>
                    {session.messageCount} 条消息 · {formatRelativeTime(session.updatedAt)}
                    <button
                      type="button"
                      className={styles.deleteButton}
                      aria-label={`删除会话：${session.topic || '未命名讨论'}`}
                      onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                    >
                      删除
                    </button>
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      ) : (
        <div className={styles.listContainer}>
          {reports.length === 0 ? (
            <div className={styles.emptyState}>暂无报告</div>
          ) : (
            reports.map(report => (
              <div
                key={report.filename}
                className={styles.sessionItem}
                onClick={() => onSelectReport(report)}
              >
                <span className={styles.sessionTopic}>{report.topic || report.filename}</span>
                <span className={styles.sessionMeta}>
                  {formatRelativeTime(report.modified_at * 1000)}
                </span>
              </div>
            ))
          )}
        </div>
      )}

      <a className={styles.settingsLink} href="#/settings">
        设置
      </a>
    </aside>
  );
}
