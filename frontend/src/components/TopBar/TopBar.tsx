import type { ConnectionStatus } from '../../hooks/useWebSocket';
import { ConnectionDot } from '../common/ConnectionDot';
import styles from './TopBar.module.css';

interface TopBarProps {
  topic: string;
  connectionStatus: ConnectionStatus;
  isReady: boolean;
  onExportMarkdown: () => void;
  onExportPdf: () => void;
  onExportScreenshot: () => void;
  onToggleSettings: () => void;
  onSaveReport: () => void;
  savedPath: string | null;
}

export function TopBar({
  topic, connectionStatus, isReady,
  onExportMarkdown, onExportPdf, onExportScreenshot,
  onToggleSettings, onSaveReport, savedPath,
}: TopBarProps) {
  return (
    <header className={styles.topBar}>
      <div className={styles.left}>
        <h1 className={styles.title}>{topic || 'Agent Discussion'}</h1>
        <ConnectionDot status={connectionStatus} />
      </div>
      <div className={styles.actions}>
        {isReady && !savedPath && (
          <button className={styles.actionButton} onClick={onSaveReport} title="保存报告">
            保存
          </button>
        )}
        {savedPath && (
          <span className={styles.savedHint}>已保存</span>
        )}
        {isReady && (
          <>
            <button className={styles.actionButton} onClick={onExportMarkdown} title="导出 Markdown">
              .md
            </button>
            <button className={styles.actionButton} onClick={onExportPdf} title="打印 PDF">
              PDF
            </button>
            <button className={styles.actionButton} onClick={onExportScreenshot} title="截图">
              截图
            </button>
          </>
        )}
        <button className={styles.settingsButton} onClick={onToggleSettings} title="设置">
          ⚙
        </button>
      </div>
    </header>
  );
}
