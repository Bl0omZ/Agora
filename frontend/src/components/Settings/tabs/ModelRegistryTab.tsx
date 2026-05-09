import { useMemo, useState } from 'react';
import type { AgentDraft, ModelProfile } from '../../../types';
import { displayAgentName } from '../../../utils/modelName';
import { AgentTag } from './AgentTag';
import styles from '../../../pages/SettingsPage.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PROVIDER_LABEL: Record<string, string> = {
  openai_compatible: 'OpenAI 兼容',
  anthropic: 'Anthropic',
  azure_openai: 'Azure OpenAI',
};

/** Parse "provider/model_id" back into parts. */
function parseAgentModel(raw: string): { provider: string; model: string } | null {
  const idx = raw.indexOf('/');
  if (idx === -1) return null;
  return { provider: raw.slice(0, idx), model: raw.slice(idx + 1) };
}

/** Build the agent model string used to reference a registry entry. */
function agentModelKey(providerName: string, modelId: string): string {
  return `${providerName}/${modelId}`;
}

interface Props {
  agents: AgentDraft[];
  models: ModelProfile[];
  onChangeModels: (next: ModelProfile[]) => void;
  onChangeAgents: (next: AgentDraft[]) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ModelRegistryTab({ agents, models, onChangeModels, onChangeAgents }: Props) {
  const [adding, setAdding] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [form, setForm] = useState<{
    name: string; provider: string; base_url: string;
    modelInput: string; key: string;
  }>({ name: '', provider: 'openai_compatible', base_url: '', modelInput: '', key: '' });
  const [showKey, setShowKey] = useState(false);

  // --- Derived data ---------------------------------------------------------

  /** Agents NOT yet pointing to any registry model. */
  const unassigned = useMemo(() => {
    const registryNames = new Set(models.map(m => m.name));
    return agents.filter(a => {
      if (!a.model) return false;
      if (registryNames.has(a.model)) return false;
      const parsed = parseAgentModel(a.model);
      return !parsed || !registryNames.has(parsed.provider);
    });
  }, [agents, models]);

  // --- Handlers -------------------------------------------------------------

  const removeProvider = (name: string) => {
    const bound = agents.filter(a => a.model.startsWith(name + '/'));
    if (bound.length > 0) {
      const names = bound.map(a => displayAgentName(a.name)).join('、');
      const ok = window.confirm(
        `删除 Provider「${name}」会同时解绑 ${bound.length} 个参与者（${names}）的模型引用，确认删除？`,
      );
      if (!ok) return;
      onChangeAgents(agents.map(a =>
        a.model.startsWith(name + '/') ? { ...a, model: '' } : a,
      ));
    } else if (!window.confirm(`删除 Provider「${name}」？`)) {
      return;
    }
    onChangeModels(models.filter(m => m.name !== name));
  };

  const openAdd = (prefill?: { name?: string }) => {
    setForm({ name: prefill?.name ?? '', provider: 'openai_compatible', base_url: '', modelInput: '', key: '' });
    setEditingName(null);
    setAdding(true);
    setShowKey(false);
  };

  const openEdit = (m: ModelProfile) => {
    setForm({ name: m.name, provider: m.provider, base_url: m.base_url, modelInput: m.models.join(', '), key: '' });
    setEditingName(m.name);
    setAdding(true);
    setShowKey(false);
  };

  const cancelForm = () => { setAdding(false); setEditingName(null); };

  const commitForm = () => {
    const name = form.name.trim();
    if (!name) return;
    const modelList = form.modelInput
      .split(/[,，\s]+/)
      .map(s => s.trim())
      .filter(Boolean);
    const clean: ModelProfile = {
      name,
      provider: form.provider,
      base_url: form.base_url.trim(),
      models: modelList,
      env_var_name: '',
    };
    const withKey = form.key.trim() ? { ...clean, key: form.key.trim() } : clean;

    if (editingName !== null) {
      onChangeModels(models.map(m => (m.name === editingName ? withKey : m)));
    } else {
      if (models.some(m => m.name === name)) {
        window.alert(`Provider 名「${name}」已存在`);
        return;
      }
      onChangeModels([...models, withKey]);
    }
    cancelForm();
  };

  /** Agent name → which provider/model they're assigned to. */
  const agentAssign = useMemo(() => {
    const map = new Map<string, { provider: string; model: string } | null>();
    for (const a of agents) {
      if (!a.model) { map.set(a.name, null); continue; }
      const parsed = parseAgentModel(a.model);
      if (parsed && models.some(m => m.name === parsed.provider)) {
        map.set(a.name, parsed);
      } else {
        map.set(a.name, null);
      }
    }
    return map;
  }, [agents, models]);

  return (
    <>
      <h3 className={styles.bodyTitle}>Model Registry</h3>
      <p className={styles.bodyHint}>
        Provider 定义连接方式和地址，下面挂多个模型。参与者引用格式为 <code>provider/模型名</code>。
        <strong>密钥脱敏展示，不会明文出现在 UI 中</strong>。
      </p>

      {/* ---- Unassigned agents ---- */}
      {unassigned.length > 0 && (
        <div className={styles.modelSummary}>
          <h3 className={styles.modelSummaryTitle}>尚未指定模型的参与者</h3>
          <div className={styles.tagRow}>
            {unassigned.map(a => <AgentTag key={a.name} name={a.name} />)}
          </div>
        </div>
      )}

      {/* ---- Provider cards ---- */}
      {models.map(m => (
        <div key={m.name} className={styles.providerCard}>
          <div className={styles.providerHeader}>
            <div>
              <span className={styles.providerName}>{m.name}</span>
              <span className={styles.providerBadge}>
                {PROVIDER_LABEL[m.provider] ?? m.provider}
              </span>
            </div>
            <div className={styles.providerActions}>
              <button type="button" className={styles.copyBtn} onClick={() => openEdit(m)}>编辑</button>
              <button type="button" className={styles.copyBtn} onClick={() => removeProvider(m.name)}>删除</button>
            </div>
          </div>

          <div className={styles.providerMeta}>
            <span className={styles.providerMetaLabel}>地址</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
              {m.base_url || <span style={{ color: 'var(--accent)' }}>请配置</span>}
            </span>
          </div>

          <div className={styles.providerMeta}>
            <span className={styles.providerMetaLabel}>密钥</span>
            <span className={styles.envName}>{m.env_var_name}</span>
            {m.key_masked ? (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-muted)' }}>
                {m.key_masked}
              </span>
            ) : (
              <span style={{ fontSize: 12, color: 'var(--accent)' }}>请配置</span>
            )}
          </div>

          <div className={styles.providerModels}>
            {m.models.map(modelId => {
              const key = agentModelKey(m.name, modelId);
              const users = agents.filter(a => a.model === key).map(a => a.name);
              return (
                <div key={modelId} className={styles.modelRow}>
                  <span className={styles.modelRowId}>{modelId}</span>
                  <div className={styles.tagRow}>
                    {users.length > 0
                      ? users.map(name => <AgentTag key={name} name={name} />)
                      : <span style={{ fontSize: 12, color: 'var(--ink-muted)' }}>未使用</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {!adding && models.length === 0 && (
        <p style={{ color: 'var(--ink-muted)', fontSize: 14, marginTop: 24 }}>
          暂无 Provider，点击下方按钮添加。
        </p>
      )}

      {/* ---- Add / Edit form ---- */}
      {adding && (
        <div className={styles.providerCard} style={{ borderColor: 'var(--accent)', borderStyle: 'dashed' }}>
          <h3 className={styles.modelSummaryTitle}>
            {editingName !== null ? `编辑 Provider：${editingName}` : '新增 Provider'}
          </h3>
          <div className={styles.formGrid}>
            <label className={styles.formField}>
              <span className={styles.formLabel}>Provider 名称</span>
              <input className={styles.textInput} value={form.name}
                disabled={editingName !== null}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="如 ant" />
            </label>
            <label className={styles.formField}>
              <span className={styles.formLabel}>连接方式</span>
              <select className={styles.select} value={form.provider}
                onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}
                style={{ minWidth: 'auto' }}>
                <option value="openai_compatible">OpenAI 兼容</option>
                <option value="anthropic">Anthropic</option>
                <option value="azure_openai">Azure OpenAI</option>
              </select>
            </label>
            <label className={styles.formField} style={{ gridColumn: '1 / -1' }}>
              <span className={styles.formLabel}>API 地址</span>
              <input className={styles.textInput} value={form.base_url}
                onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                placeholder="https://api.example.com/v1" />
            </label>
            <label className={styles.formField} style={{ gridColumn: '1 / -1' }}>
              <span className={styles.formLabel}>模型列表</span>
              <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                逗号或空格分隔，如 GLM-5.1, Kimi-K2.6
              </span>
              <input className={styles.textInput} value={form.modelInput}
                onChange={e => setForm(f => ({ ...f, modelInput: e.target.value }))}
                placeholder="GLM-5.1, Kimi-K2.6" />
            </label>
            <label className={styles.formField} style={{ gridColumn: '1 / -1' }}>
              <span className={styles.formLabel}>API Key</span>
              <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                密钥将写入 .env 变量 {form.name.trim().toUpperCase().replace(/[^A-Z0-9]/g, '_') || 'ANT'}_API_KEY
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <input className={styles.textInput} type={showKey ? 'text' : 'password'} value={form.key}
                  onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
                  placeholder="sk-..." style={{ flex: 1 }} />
                <button type="button" className={styles.copyBtn}
                  onClick={() => setShowKey(v => !v)}
                  style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>
                  {showKey ? '隐藏' : '显示'}
                </button>
              </div>
              {form.key.trim() && (
                <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                  保存后显示为：{form.key.trim().length <= 8
                    ? form.key.trim().slice(0, 2) + '****' + form.key.trim().slice(-2)
                    : form.key.trim().slice(0, 6) + '****' + form.key.trim().slice(-4)}
                </span>
              )}
            </label>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <button type="button" className={styles.saveBtn} onClick={commitForm}>
              {editingName !== null ? '保存修改' : '添加 Provider'}
            </button>
            <button type="button" className={styles.copyBtn} onClick={cancelForm}>取消</button>
          </div>
        </div>
      )}

      {!adding && (
        <button type="button" className={styles.addBtn} onClick={() => openAdd()}>
          + 添加 Provider
        </button>
      )}
    </>
  );
}
