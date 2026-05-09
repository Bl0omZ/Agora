import { useCallback, useEffect, useState } from 'react';
import type { AppConfigPublic } from '../types';

interface FetchState {
  config: AppConfigPublic | null;
  etag: string | null;
  loading: boolean;
  error: string | null;
}

export interface SaveResult {
  ok: boolean;
  etag?: string;
  error?: { status: 409 | 422; detail: string; field?: string };
}

const SUB_ROUTES = ['models', 'agents', 'presets', 'runtime'] as const;
type SubRoute = (typeof SUB_ROUTES)[number];

/**
 * 串行保存 4 个 sub-route。每次 PUT 拿到的新 ETag 用于下一次 If-Match。
 * 任一 PUT 返回 409/422 → 停止，把错误抛回 UI。
 */
async function saveSubRoute(
  route: SubRoute,
  payload: unknown,
  etag: string | null,
): Promise<SaveResult> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (etag) headers['If-Match'] = etag;
  const resp = await fetch(`/api/config/${route}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(payload),
  });
  const newEtag = resp.headers.get('ETag') || undefined;
  if (resp.ok) return { ok: true, etag: newEtag };
  let detail = '';
  let field: string | undefined;
  try {
    const body = await resp.json();
    detail = body?.detail ?? body?.error?.detail ?? '';
    field = body?.error?.field;
  } catch { /* ignore */ }
  if (resp.status === 409) return { ok: false, error: { status: 409, detail: detail || 'config_modified_elsewhere' } };
  if (resp.status === 422) return { ok: false, error: { status: 422, detail: detail || 'schema_invalid', field } };
  return { ok: false, error: { status: 422, detail: detail || `HTTP ${resp.status}` } };
}

export function useConfigApi() {
  const [state, setState] = useState<FetchState>({
    config: null,
    etag: null,
    loading: false,
    error: null,
  });

  const fetchConfig = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const resp = await fetch('/api/config');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const config = (await resp.json()) as AppConfigPublic;
      const etag = resp.headers.get('ETag');
      setState({ config, etag, loading: false, error: null });
    } catch (e) {
      setState(s => ({ ...s, loading: false, error: e instanceof Error ? e.message : 'fetch failed' }));
    }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const saveAll = useCallback(async (
    draft: AppConfigPublic,
    initialEtag: string | null,
  ): Promise<SaveResult> => {
    let currentEtag = initialEtag;
    const slices: Record<SubRoute, unknown> = {
      models: draft.models ?? [],
      agents: draft.agents,
      presets: draft.presets ?? [],
      runtime: draft.runtime,
    };
    for (const route of SUB_ROUTES) {
      const r = await saveSubRoute(route, slices[route], currentEtag);
      if (!r.ok) return r;
      if (r.etag) currentEtag = r.etag;
    }
    if (currentEtag) setState(s => ({ ...s, etag: currentEtag }));
    return { ok: true, etag: currentEtag ?? undefined };
  }, []);

  return {
    config: state.config,
    etag: state.etag,
    loading: state.loading,
    error: state.error,
    refetch: fetchConfig,
    saveAll,
  };
}
