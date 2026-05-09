import { useEffect, useState } from 'react';
import type { PresetRecommendation } from '../../types';
import { displayAgentName } from '../../utils/modelName';
import styles from './PresetSelector.module.css';

interface PresetSelectorProps {
  recommendation: PresetRecommendation;
  onConfirm: (presetName: string) => void;
}

export function PresetSelector({ recommendation, onConfirm }: PresetSelectorProps) {
  const [selected, setSelected] = useState(recommendation.recommended);

  useEffect(() => {
    setSelected(recommendation.recommended);
  }, [recommendation.recommended]);

  const selectedPreset = recommendation.presets.find((preset) => preset.name === selected);
  const canConfirm = Boolean(selectedPreset);

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div>
          <span className={styles.title}>选择讨论模式</span>
          <span className={styles.titleHint}>主持人已推荐本轮参与者组合</span>
        </div>
      </div>

      <div className={styles.list}>
        {recommendation.presets.map((preset) => {
          const isSelected = preset.name === selected;
          const isRecommended = preset.name === recommendation.recommended;
          return (
            <button
              key={preset.name}
              type="button"
              className={`${styles.option} ${isSelected ? styles.selected : ''} ${isRecommended ? styles.recommended : ''}`}
              onClick={() => setSelected(preset.name)}
            >
              <span className={styles.radio} />
              <span className={styles.optionBody}>
                <span className={styles.optionTitle}>
                  {preset.label}
                  {isRecommended && <span className={styles.badge}>推荐</span>}
                </span>
                <span className={styles.description}>{preset.description}</span>
                <span className={styles.agents}>
                  参与者：{preset.agents.map((agent) => displayAgentName(agent.name)).join(' · ')}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          className={styles.ctaPrimary}
          disabled={!canConfirm}
          onClick={() => onConfirm(selected)}
        >
          确认开始讨论 →
        </button>
      </div>
    </div>
  );
}
