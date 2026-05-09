import { useMemo, useState, useRef, useEffect } from 'react';
import type { AgentDraft, ModelProfile } from '../../../types';
import { displayModelName, displayAgentName } from '../../../utils/modelName';
import styles from '../../../pages/SettingsPage.module.css';

function avatarLetter(name: string): string {
  return name.trim()[0]?.toUpperCase() || '?';
}

interface Props {
  agents: AgentDraft[];
  models: ModelProfile[];
  onChange: (next: AgentDraft[]) => void;
}

export function AgentsTab({ agents, models, onChange }: Props) {
  const setAgent = (idx: number, patch: Partial<AgentDraft>) => {
    onChange(agents.map((a, i) => (i === idx ? { ...a, ...patch } : a)));
  };

  const allModelOptions = useMemo(() => {
    const opts: { value: string; label: string; group: string }[] = [];
    const seen = new Set<string>();
    for (const m of models) {
      for (const mid of m.models) {
        const key = `${m.name}/${mid}`;
        if (!seen.has(key)) {
          seen.add(key);
          opts.push({ value: key, label: `${m.name} / ${mid}`, group: 'Registry' });
        }
      }
    }
    for (const a of agents) {
      const raw = a.model;
      if (!raw || seen.has(raw)) continue;
      seen.add(raw);
      opts.push({ value: raw, label: displayModelName(raw), group: '旧格式' });
    }
    return opts;
  }, [agents, models]);

  return (
    <>
      <h3 className={styles.bodyTitle}>参与者清单</h3>
      <p className={styles.bodyHint}>
        每位参与者绑定一个模型（格式 <code>provider/模型名</code>）。切换为 Registry 模型后使用 provider 的连接方式和密钥。
      </p>
      <div className={styles.list} role="list">
        {agents.map((a, idx) => (
          <div key={a.name} className={styles.agentRow} data-agent={a.name} role="listitem">
            <div className={styles.agentAvatar}>{avatarLetter(a.name)}</div>
            <div className={styles.agentInfo}>
              <span className={styles.agentInfoName}>{displayAgentName(a.name)}</span>
              <span className={styles.agentInfoDesc}>{a.description}</span>
            </div>
            <ModelPicker
              value={a.model}
              options={allModelOptions}
              onChange={(v) => setAgent(idx, { model: v })}
              label={displayAgentName(a.name)}
            />
          </div>
        ))}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// ModelPicker — custom dropdown
// ---------------------------------------------------------------------------

interface PickerOption {
  value: string;
  label: string;
  group: string;
}

function ModelPicker({ value, options, onChange, label }: {
  value: string;
  options: PickerOption[];
  onChange: (v: string) => void;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find(o => o.value === value);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('click', onClick);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('click', onClick); };
  }, [open]);

  // Group options
  const groups = useMemo(() => {
    const map = new Map<string, PickerOption[]>();
    for (const o of options) {
      const arr = map.get(o.group);
      if (arr) arr.push(o);
      else map.set(o.group, [o]);
    }
    return map;
  }, [options]);

  return (
    <div ref={ref} className={styles.picker} role="combobox" aria-expanded={open} aria-label={`${label} 的模型`}>
      <button
        type="button"
        className={`${styles.pickerTrigger} ${open ? styles.pickerTriggerOpen : ''}`}
        onClick={() => setOpen(v => !v)}
      >
        <span className={styles.pickerValue}>
          {selected?.label ?? value}
        </span>
        <svg className={styles.pickerArrow} width="12" height="12" viewBox="0 0 12 12" aria-hidden>
          <path d="M3 5l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {open && (
        <div className={styles.pickerMenu}>
          {Array.from(groups.entries()).map(([group, items]) => (
            <div key={group}>
              <div className={styles.pickerGroupLabel}>{group}</div>
              {items.map(o => (
                <button
                  key={o.value}
                  type="button"
                  className={`${styles.pickerOption} ${o.value === value ? styles.pickerOptionActive : ''}`}
                  onClick={() => { onChange(o.value); setOpen(false); }}
                >
                  {o.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
