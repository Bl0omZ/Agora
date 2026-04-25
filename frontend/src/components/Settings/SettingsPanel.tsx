import { useState } from 'react';
import type { DiscussionConfig } from '../../types';
import styles from './SettingsPanel.module.css';

interface SettingsPanelProps {
  onClose: () => void;
  onApply: (config: DiscussionConfig) => void;
  currentConfig: DiscussionConfig;
}

export function SettingsPanel({ onClose, onApply, currentConfig }: SettingsPanelProps) {
  const [maxRounds, setMaxRounds] = useState(currentConfig.maxRounds);
  const [model, setModel] = useState(currentConfig.model ?? '');

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>讨论设置</h3>
          <button className={styles.closeButton} onClick={onClose}>✕</button>
        </div>

        <div className={styles.body}>
          <label className={styles.field}>
            <span className={styles.label}>讨论轮数</span>
            <div className={styles.sliderRow}>
              <input
                type="range"
                min={1}
                max={10}
                value={maxRounds}
                onChange={(e) => setMaxRounds(Number(e.target.value))}
                className={styles.slider}
              />
              <span className={styles.sliderValue}>{maxRounds}</span>
            </div>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>模型</span>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="留空使用默认模型"
              className={styles.input}
            />
          </label>
        </div>

        <div className={styles.footer}>
          <button className={styles.cancelButton} onClick={onClose}>取消</button>
          <button
            className={styles.applyButton}
            onClick={() => {
              onApply({ maxRounds, model: model || null });
              onClose();
            }}
          >
            应用
          </button>
        </div>
      </div>
    </div>
  );
}
