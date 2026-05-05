import { useEffect, useState } from 'react';
import type { PresetRecommendation } from '../../types';
import styles from './PresetSelector.module.css';

const AGENT_DISPLAY_NAMES: Record<string, string> = {
  Architect: '架构师',
  Pragmatist: '务实派',
  Challenger: '挑战者',
  Evaluator: '评估师',
  RequirementsAnalyst: '需求分析师',
  DomainExpert: '领域专家',
  ProcessDesigner: '流程设计师',
  RootCauseAnalyst: '根因分析师',
};

function getAgentDisplayName(name: string): string {
  return AGENT_DISPLAY_NAMES[name] ?? name;
}

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
                  参与者：{preset.agents.map((agent) => getAgentDisplayName(agent.name)).join(' · ')}
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
