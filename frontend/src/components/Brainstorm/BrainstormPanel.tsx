import { useEffect, useMemo, useState } from 'react';
import type { BrainstormAnswer, BrainstormQuestion } from '../../types';
import styles from './BrainstormPanel.module.css';

interface BrainstormPanelProps {
  question: BrainstormQuestion;
  /** 提交按钮是否禁用（外部正在等待响应时传 true） */
  submitting?: boolean;
  /** 用户提交答案。 */
  onSubmit: (answer: BrainstormAnswer) => void;
  /** 用户点击「跳过澄清，直接开始讨论」。组件本身不做 confirm，留给上层 modal。 */
  onSkip: () => void;
}

/**
 * BrainstormPanel —— 议题精炼阶段的底部交互卡片。
 *
 * 设计要点：
 * 1. 主持人发问 + 候选 chip + 自由输入三段竖排，避免左右两栏的密集感。
 * 2. 单/多选由 question.allow_multiple 决定，UI 逻辑保持一致（均为 chip toggle）。
 * 3. 跳过按钮放右上角 link 风格 = 始终可达但不诱导。
 * 4. 提交按钮：必须有 selectedOption 或 freeformText 之一才可用，避免空提交。
 *
 * 不负责的事：
 * - 不弹 confirm modal（由上层 BrainstormStates 渲染）
 * - 不显示 Host 之前几轮的发问（由 Timeline 负责）
 * - 不管 5 分钟超时计时（由 hooks 层管理）
 */
export function BrainstormPanel({
  question,
  submitting = false,
  onSubmit,
  onSkip,
}: BrainstormPanelProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [freeformText, setFreeformText] = useState('');

  // 切换问题时清空之前的选择，避免串状态
  useEffect(() => {
    setSelectedIds([]);
    setFreeformText('');
  }, [question.id]);

  const toggleOption = (optionId: string) => {
    if (submitting) return;
    if (question.allow_multiple) {
      setSelectedIds((prev) =>
        prev.includes(optionId) ? prev.filter((id) => id !== optionId) : [...prev, optionId],
      );
    } else {
      setSelectedIds((prev) => (prev[0] === optionId ? [] : [optionId]));
    }
  };

  const canSubmit = useMemo(() => {
    if (submitting) return false;
    return selectedIds.length > 0 || freeformText.trim().length > 0;
  }, [selectedIds, freeformText, submitting]);

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit({
      question_id: question.id,
      selected_option_ids: selectedIds,
      freeform_text: freeformText.trim(),
    });
  };

  return (
    <div className={styles.panel}>
      {/* 进度 + 跳过 link */}
      <div className={styles.header}>
        <span className={styles.progress}>
          议题精炼 ·{' '}
          <span className={styles.progressEmphasis}>
            第 {question.round} / {question.max_rounds} 轮
          </span>
        </span>
        <button
          type="button"
          className={styles.skipLink}
          onClick={onSkip}
          disabled={submitting}
        >
          跳过澄清，直接开始讨论 →
        </button>
      </div>

      {/* 主持人发问气泡 */}
      <div className={styles.questionRow}>
        <span className={styles.avatar}>H</span>
        <div className={styles.questionContent}>
          <div className={styles.questionMeta}>
            <span className={styles.authorName}>主持人</span>
            <span className={styles.badge}>主持人</span>
          </div>
          <div className={styles.questionText}>{question.question}</div>
        </div>
      </div>

      {/* 候选 chip */}
      {question.options.length > 0 && (
        <div className={styles.optionsList}>
          {question.options.map((opt) => {
            const isSelected = selectedIds.includes(opt.id);
            return (
              <button
                key={opt.id}
                type="button"
                disabled={submitting}
                className={`${styles.option} ${isSelected ? styles.selected : ''}`}
                onClick={() => toggleOption(opt.id)}
              >
                {isSelected && <span className={styles.checkMark} />}
                {opt.label}
              </button>
            );
          })}
        </div>
      )}

      {/* 自由输入 */}
      {question.allow_freeform && (
        <div className={styles.freeformWrap}>
          <label className={styles.freeformLabel}>
            补充说明（可选）
          </label>
          <textarea
            className={styles.freeformInput}
            value={freeformText}
            onChange={(e) => setFreeformText(e.target.value)}
            placeholder="如果上面的选项不够准确，可以在这里补充你的想法…"
            disabled={submitting}
          />
        </div>
      )}

      {/* 提交 */}
      <div className={styles.footer}>
        <span className={styles.hint}>
          {question.allow_multiple ? '可多选' : '单选'}
          {question.allow_freeform && '，或自由补充'}
        </span>
        <button
          type="button"
          className={styles.submitButton}
          onClick={handleSubmit}
          disabled={!canSubmit}
        >
          {submitting ? '提交中…' : '提交回答'}
        </button>
      </div>
    </div>
  );
}
