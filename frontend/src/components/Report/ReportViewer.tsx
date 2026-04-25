import { useState, useEffect, useMemo } from 'react';
import type { ReportEntry } from '../../types';
import { renderMarkdown } from '../../utils/markdown';
import styles from './ReportViewer.module.css';

interface ReportViewerProps {
  report: ReportEntry;
  onClose: () => void;
}

export function ReportViewer({ report, onClose }: ReportViewerProps) {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/reports/${report.filename}`)
      .then(res => res.text())
      .then(text => { setContent(text); setLoading(false); })
      .catch(() => { setContent('加载失败'); setLoading(false); });
  }, [report.filename]);

  const htmlContent = useMemo(() => renderMarkdown(content), [content]);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.viewer} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>{report.topic || report.filename}</h3>
          <button className={styles.closeButton} onClick={onClose}>✕</button>
        </div>
        <div className={styles.body}>
          {loading ? (
            <div className={styles.loading}>加载中…</div>
          ) : (
            <div
              className="markdown-content"
              dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
