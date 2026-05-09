/**
 * Display-only helpers for cleaning yaml env-var templates in model fields.
 *
 * 后端 GET /api/config 透传 yaml 原值，agent.model 可能是 `${REQ_ANALYST_MODEL:-GLM-5.1}` 这种
 * envar 模板字符串。展示时优先显示 fallback 值（`:-` 后的字符串），保留原值用于 PUT 回写。
 */

const ENV_TEMPLATE_RE = /^\$\{([^:}]+)(?::-(.*?))?\}$/;

/**
 * 清洗显示用的 model 字符串。
 * `${REQ_ANALYST_MODEL:-GLM-5.1}` → `GLM-5.1`
 * `${X:-}` → 'X'（变量名兜底）
 * `mimo-v2.5-pro` → `mimo-v2.5-pro`（无模板原样返回）
 */
export function displayModelName(raw: string): string {
  const m = ENV_TEMPLATE_RE.exec(raw);
  if (!m) return raw;
  const [, varName, fallback] = m;
  if (fallback && fallback.length > 0) return fallback;
  return varName;
}

/** 检测一个 model 字符串是否为 envar 模板（用于 UI 标记"读自环境变量"）。 */
export function isEnvTemplate(raw: string): boolean {
  return ENV_TEMPLATE_RE.test(raw);
}

// ---------------------------------------------------------------------------
// Agent 名称中英文映射
// ---------------------------------------------------------------------------

const AGENT_ZH: Record<string, string> = {
  Host: '主持人',
  Architect: '架构师',
  Pragmatist: '务实派',
  Challenger: '挑战者',
  RequirementsAnalyst: '需求分析师',
  DomainExpert: '领域专家',
  Evaluator: '评估者',
  ProcessDesigner: '流程设计师',
  RootCauseAnalyst: '根因分析师',
  Synthesizer: '总结者',
};

/** 将 agent 英文名转为 "中文（English）" 格式，未知名称原样返回。 */
export function displayAgentName(en: string): string {
  const zh = AGENT_ZH[en];
  return zh ? `${zh}（${en}）` : en;
}
