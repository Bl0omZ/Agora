import { useState } from 'react';
import type { PresetDraft, AgentDraft } from '../../../types';
import { displayAgentName } from '../../../utils/modelName';
import styles from '../../../pages/SettingsPage.module.css';

function letter(name: string): string {
  return name.trim()[0]?.toUpperCase() || '?';
}

interface Props {
  presets: PresetDraft[];
  agents: AgentDraft[];
  onChange: (next: PresetDraft[]) => void;
}

export function PresetsTab({ presets, agents, onChange }: Props) {
  const [editingIdx, setEditingIdx] = useState<number | null>(null);

  const handleCopy = (idx: number) => {
    const src = presets[idx];
    const baseName = `${src.name}-copy`;
    let suffix = 1;
    let candidate = baseName;
    while (presets.some(p => p.name === candidate)) {
      suffix += 1;
      candidate = `${baseName}-${suffix}`;
    }
    const copy: PresetDraft = {
      name: candidate,
      label: `${src.label}（副本）`,
      description: src.description,
      agents: [...src.agents],
    };
    const next = [...presets, copy];
    onChange(next);
    setEditingIdx(next.length - 1);
  };

  const handleDelete = (idx: number) => {
    const p = presets[idx];
    if (!window.confirm(`删除 preset「${p.label || p.name}」？`)) return;
    if (editingIdx === idx) setEditingIdx(null);
    onChange(presets.filter((_, i) => i !== idx));
  };

  const setPreset = (idx: number, patch: Partial<PresetDraft>) => {
    onChange(presets.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  };

  const toggleAgent = (idx: number, agentName: string, agentDesc: string) => {
    const preset = presets[idx];
    const exists = preset.agents.some(a => a.name === agentName);
    if (exists) {
      setPreset(idx, { agents: preset.agents.filter(a => a.name !== agentName) });
    } else {
      setPreset(idx, { agents: [...preset.agents, { name: agentName, description: agentDesc }] });
    }
  };

  return (
    <>
      <h3 className={styles.bodyTitle}>Preset 清单</h3>
      <p className={styles.bodyHint}>
        Preset 是「一组参与者 + 描述」的组合。点击「编辑」可修改名称、描述和包含的参与者；点击「复制」创建副本。修改后点页面顶部「保存」写回配置。
      </p>
      <div className={styles.presetGrid}>
        {presets.map((p, idx) => {
          const isEditing = editingIdx === idx;
          return (
            <div key={p.name} className={`${styles.presetCard} ${isEditing ? styles.presetCardEditing : ''}`}>
              {isEditing ? (
                <div className={styles.presetEditBody}>
                  <label className={styles.presetEditField}>
                    <span className={styles.presetEditLabel}>名称 (name)</span>
                    <input
                      className={styles.textInput}
                      value={p.name}
                      onChange={e => setPreset(idx, { name: e.target.value })}
                    />
                  </label>
                  <label className={styles.presetEditField}>
                    <span className={styles.presetEditLabel}>显示名 (label)</span>
                    <input
                      className={styles.textInput}
                      value={p.label}
                      onChange={e => setPreset(idx, { label: e.target.value })}
                    />
                  </label>
                  <label className={styles.presetEditField}>
                    <span className={styles.presetEditLabel}>描述</span>
                    <textarea
                      className={styles.textInput}
                      rows={2}
                      value={p.description}
                      onChange={e => setPreset(idx, { description: e.target.value })}
                    />
                  </label>
                  <div className={styles.presetEditField}>
                    <span className={styles.presetEditLabel}>包含参与者</span>
                    <div className={styles.presetAgentChecklist}>
                      {agents.map(a => (
                        <label key={a.name} className={styles.presetAgentCheck}>
                          <input
                            type="checkbox"
                            checked={p.agents.some(pa => pa.name === a.name)}
                            onChange={() => toggleAgent(idx, a.name, a.description)}
                          />
                          <span>{displayAgentName(a.name)}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <button className={styles.copyBtn} type="button" onClick={() => setEditingIdx(null)}>
                    完成
                  </button>
                </div>
              ) : (
                <>
                  <div className={styles.presetHead}>
                    <h4 className={styles.presetName}>{p.label || p.name}</h4>
                    <div className={styles.presetActions}>
                      <button className={styles.copyBtn} type="button" onClick={() => setEditingIdx(idx)}>
                        编辑
                      </button>
                      <button className={styles.copyBtn} type="button" onClick={() => handleCopy(idx)}>
                        复制
                      </button>
                      <button className={styles.copyBtn} type="button" onClick={() => handleDelete(idx)}>
                        删除
                      </button>
                    </div>
                  </div>
                  <p className={styles.presetDesc}>{p.description || p.name}</p>
                  <div className={styles.presetDots} aria-label={`包含 ${p.agents.length} 个参与者`}>
                    {p.agents.map(a => (
                      <span key={a.name} className={styles.dot} data-agent={a.name} title={displayAgentName(a.name)}>
                        {letter(a.name)}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
