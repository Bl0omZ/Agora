import { useEffect, useState } from 'react';
import type {
  AppConfigPublic,
  AgentDraft,
  PresetDraft,
  RuntimeParams,
  ModelProfile,
} from '../types';
import { AgentsTab } from '../components/Settings/tabs/AgentsTab';
import { PresetsTab } from '../components/Settings/tabs/PresetsTab';
import { RuntimeTab } from '../components/Settings/tabs/RuntimeTab';
import { ModelRegistryTab } from '../components/Settings/tabs/ModelRegistryTab';
import styles from './SettingsPage.module.css';

type TabKey = 'agents' | 'presets' | 'runtime' | 'models';

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'agents', label: '参与者' },
  { key: 'presets', label: 'Presets' },
  { key: 'runtime', label: '运行参数' },
  { key: 'models', label: 'Model Registry' },
];

function readTabFromHash(): TabKey {
  const m = /tab=([a-z]+)/.exec(window.location.hash);
  const found = m?.[1] as TabKey | undefined;
  return found && TABS.some(t => t.key === found) ? found : 'agents';
}

interface ToastState {
  kind: 'success' | 'warn' | 'error';
  message: string;
}

interface Props {
  /** 初始配置；接入 useConfigApi 之前由父级或 fixture 注入。 */
  initialConfig: AppConfigPublic;
  /** 当前 ETag；PUT 时回填到 If-Match。 */
  etag: string | null;
  /** 保存：返回 Promise<{ ok, etag?, error? }>。父级实现，骨架阶段可 mock。 */
  onSave: (config: AppConfigPublic, etag: string | null) => Promise<{
    ok: boolean;
    etag?: string;
    error?: { status: 409 | 422; detail: string; field?: string };
  }>;
  /** 返回主页面回调。 */
  onBack: () => void;
}

export function SettingsPage({ initialConfig, etag, onSave, onBack }: Props) {
  const [tab, setTab] = useState<TabKey>(readTabFromHash);
  const [draft, setDraft] = useState<AppConfigPublic>(initialConfig);
  const [currentEtag, setCurrentEtag] = useState<string | null>(etag);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    const onHash = () => setTab(readTabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    if (!toast) return;
    if (toast.kind === 'error') return; // 错误 toast 由用户手动关闭（hover 持久化方案待定）
    const id = window.setTimeout(() => setToast(null), 1800);
    return () => window.clearTimeout(id);
  }, [toast]);

  const goTab = (key: TabKey) => {
    window.location.hash = `#/settings?tab=${key}`;
  };

  const updateAgents = (next: AgentDraft[]) => { setDraft(d => ({ ...d, agents: next })); setDirty(true); };
  const updatePresets = (next: PresetDraft[]) => { setDraft(d => ({ ...d, presets: next })); setDirty(true); };
  const updateRuntime = (next: RuntimeParams) => { setDraft(d => ({ ...d, runtime: next })); setDirty(true); };
  const updateModels = (next: ModelProfile[]) => { setDraft(d => ({ ...d, models: next })); setDirty(true); };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const result = await onSave(draft, currentEtag);
      if (result.ok) {
        if (result.etag) setCurrentEtag(result.etag);
        setDirty(false);
        setToast({ kind: 'success', message: '已保存' });
      } else if (result.error?.status === 409) {
        setToast({ kind: 'warn', message: '配置已被另一处修改，请刷新' });
      } else if (result.error?.status === 422) {
        const field = result.error.field ? `（字段：${result.error.field}）` : '';
        setToast({ kind: 'error', message: `${result.error.detail}${field}` });
      } else {
        setToast({ kind: 'error', message: '保存失败' });
      }
    } catch (e) {
      setToast({ kind: 'error', message: e instanceof Error ? e.message : '网络异常' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.topbar}>
          <button className={styles.back} onClick={onBack} type="button">‹ 返回</button>
          <h2 className={styles.topTitle}>讨论设置</h2>
          <div className={styles.topActions}>
            <a className={styles.exportLink} href="/api/config/export" download>导出当前配置</a>
            <button
              className={`${styles.saveBtn} ${dirty ? styles.saveBtnDirty : ''}`}
              disabled={!dirty || saving}
              onClick={handleSave}
              type="button"
            >
              {saving ? '保存中…' : '保存'}
            </button>
          </div>
        </div>

        <div className={styles.tabs} role="tablist">
          {TABS.map(t => (
            <button
              key={t.key}
              className={`${styles.tab} ${tab === t.key ? styles.tabActive : ''}`}
              onClick={() => goTab(t.key)}
              role="tab"
              aria-selected={tab === t.key}
              type="button"
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className={styles.body}>
        {tab === 'agents' && (
          <AgentsTab
            agents={draft.agents}
            models={draft.models ?? []}
            onChange={updateAgents}
          />
        )}
        {tab === 'presets' && (
          <PresetsTab
            presets={draft.presets ?? []}
            agents={draft.agents}
            onChange={updatePresets}
          />
        )}
        {tab === 'runtime' && (
          <RuntimeTab
            runtime={draft.runtime}
            models={draft.models ?? []}
            onChange={updateRuntime}
          />
        )}
        {tab === 'models' && (
          <ModelRegistryTab
            agents={draft.agents}
            models={draft.models ?? []}
            onChangeModels={updateModels}
            onChangeAgents={updateAgents}
          />
        )}
      </div>
      </div>

      {toast && (
        <div
          className={`${styles.toast} ${
            toast.kind === 'success' ? styles.toastSuccess :
            toast.kind === 'warn' ? styles.toastWarn :
            styles.toastError
          }`}
          role="status"
          onClick={() => setToast(null)}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
