import type { RuntimeParams, ModelProfile } from '../../../types';
import styles from '../../../pages/SettingsPage.module.css';

interface Props {
  runtime: RuntimeParams;
  models: ModelProfile[];
  onChange: (next: RuntimeParams) => void;
}

export function RuntimeTab({ runtime, models, onChange }: Props) {
  const set = <K extends keyof RuntimeParams>(key: K, value: RuntimeParams[K]) => {
    onChange({ ...runtime, [key]: value });
  };

  return (
    <>
      <h3 className={styles.bodyTitle}>运行参数</h3>
      <p className={styles.bodyHint}>
        这里聚合了 brainstorm / discussion / voting / synthesizer 四个阶段的关键运行参数。修改后保存会回写到 yaml 对应字段，yaml schema 不变。
      </p>
      <div className={styles.fieldList}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>讨论轮数</span>
          <div className={styles.fieldControl}>
            <input
              type="range"
              min={1}
              max={10}
              className={styles.slider}
              value={runtime.max_rounds}
              onChange={(e) => set('max_rounds', Number(e.target.value))}
            />
            <span className={styles.sliderValue}>{runtime.max_rounds}</span>
          </div>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>议题精炼</span>
          <div className={styles.fieldControl}>
            <span
              className={`${styles.toggle} ${runtime.brainstorm_enabled ? styles.toggleOn : ''}`}
              role="switch"
              aria-checked={runtime.brainstorm_enabled}
              tabIndex={0}
              onClick={() => set('brainstorm_enabled', !runtime.brainstorm_enabled)}
              onKeyDown={(e) => {
                if (e.key === ' ' || e.key === 'Enter') {
                  e.preventDefault();
                  set('brainstorm_enabled', !runtime.brainstorm_enabled);
                }
              }}
            />
            <span className={styles.fieldHint}>
              {runtime.brainstorm_enabled ? '启用主持人议题精炼' : '直接进入讨论'}
            </span>
          </div>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>投票超时</span>
          <div className={styles.fieldControl}>
            <input
              type="number"
              min={30}
              max={600}
              step={10}
              className={styles.numberInput}
              value={runtime.voting_timeout_s}
              onChange={(e) => set('voting_timeout_s', Number(e.target.value))}
            />
            <span className={styles.fieldHint}>秒（30 – 600）</span>
          </div>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>总结模型</span>
          <div className={styles.fieldControl}>
            <select
              className={styles.select}
              value={runtime.summary_model ?? ''}
              onChange={(e) => set('summary_model', e.target.value === '' ? null : e.target.value)}
            >
              <option value="">沿用 discussion 默认</option>
              {models.map(m =>
                m.models.map(mid => (
                  <option key={`${m.name}/${mid}`} value={`${m.name}/${mid}`}>
                    {m.name} / {mid}
                  </option>
                ))
              )}
            </select>
            <span className={styles.fieldHint}>
              {runtime.summary_model === null || runtime.summary_model === undefined ? '未指定' : runtime.summary_model}
            </span>
          </div>
        </label>
      </div>
    </>
  );
}
