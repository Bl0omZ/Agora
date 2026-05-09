export interface AgentInfo {
  name: string;
  description: string;
  model: string;
  final_only: boolean;
  is_moderator?: boolean;
}

export interface Message {
  id: number;
  name: string;
  content: string;
  phase: string;
  role: string;
  timestamp: number;
  meta?: HostMessageMeta;
}

export interface PhaseEvent {
  phase: string;
  label: string;
  timestamp: number;
}

export interface Vote {
  agent_name: string;
  stance: string;
  reason: string;
  confidence: number;
  source?: string;
}

export interface VotingResult {
  votes: Vote[];
  conclusion: string;
}

export interface BlueprintAgentSpec {
  name: string;
  role: string;
  goal: string;
  instructions: string;
  inputs: string[];
  outputs: string[];
  collaboration_rules: string[];
}

export interface WorkflowStep {
  id: string;
  name: string;
  owner_agent: string;
  input: string;
  output: string;
  next: string[];
  error_path: string;
}

export interface AgentSystemBlueprint {
  schema_version: number;
  id: string;
  project_id?: string | null;
  session_id?: string | null;
  name: string;
  status: 'draft' | 'reviewed' | 'exported';
  problem_statement: string;
  target_user: string;
  use_cases: string[];
  non_goals: string[];
  input_contract: { description: string; examples: string[]; required_fields: string[] };
  output_contract: { description: string; format: string; required_sections: string[] };
  workflow: { steps: WorkflowStep[] };
  agents: BlueprintAgentSpec[];
  tools: Array<Record<string, unknown>>;
  evaluation: { criteria: string[]; test_cases: string[] };
  risks: Array<{ risk: string; mitigation: string; severity: string }>;
  exports: Array<Record<string, unknown>>;
  generation: { source: string; warnings: string[] };
}

export type BlueprintExportFormat = 'markdown' | 'json' | 'yaml' | 'prompt_pack';

export type AgentStatus = 'idle' | 'thinking' | 'spoken' | 'skipped';

export interface AgentState {
  name: string;
  status: AgentStatus;
  speakCount: number;
}

export type DiscussionPhase =
  | 'idle'
  | 'brainstorming'
  | 'discussion'
  | 'synthesis'
  | 'blueprint'
  | 'voting'
  | 'followup'
  | 'followup_round'
  | 'done';

export interface RoundProgress {
  current: number;
  total: number;
}

export interface PipelineLog {
  phase: string;
  event: string;
  timestamp: number;
  durationMs?: number;
  tokens?: number;
  detail?: string;
}

export interface SessionData {
  schemaVersion: number;
  id: string;
  topic: string;
  messages: Message[];
  phases: PhaseEvent[];
  votingResult: VotingResult | null;
  blueprint?: AgentSystemBlueprint | null;
  blueprintWarnings?: string[];
  discussionSummary?: DiscussionSummary | null;
  logs: PipelineLog[];
  savedPath: string | null;
  createdAt: number;
  updatedAt: number;
}

export interface SessionIndexEntry {
  id: string;
  topic: string;
  messageCount: number;
  createdAt: number;
  updatedAt: number;
}

export interface ReportEntry {
  filename: string;
  topic: string;
  size_bytes: number;
  modified_at: number;
  path: string;
}

export interface DiscussionConfig {
  maxRounds: number;
  model: string | null;
}

export interface ActiveFilters {
  roles: string[];
  phases: string[];
}

// =============================================================================
// Brainstorming · Moderator topic refinement
// =============================================================================

/**
 * 主持人发起的一轮提问的选项。
 */
export interface BrainstormOption {
  id: string;
  label: string;
}

/**
 * 主持人发起的一轮提问。对应 WS 事件 `moderator_question`。
 */
export interface BrainstormQuestion {
  /** 该问题的唯一 id（同一 brainstorm session 内单调递增）。 */
  id: string;
  /** 当前是第几轮（1-based），用于在 UI 上显示「第 N 轮 / 共 M 轮」。 */
  round: number;
  /** 该 brainstorm 配置的最大轮数，主要用于进度提示。 */
  max_rounds: number;
  /** 主持人提出的具体问题文本。 */
  question: string;
  /** 主持人给出的候选选项；可能为空（纯自由输入）。 */
  options: BrainstormOption[];
  /** 是否允许多选；single 时前端按 radio 渲染，multi 时按 chip toggle。 */
  allow_multiple: boolean;
  /** 是否允许补充自由文本，前端是否渲染补充输入框。 */
  allow_freeform: boolean;
}

/**
 * 用户对一轮提问的回答。对应 WS 事件 `moderator_answer`。
 */
export interface BrainstormAnswer {
  question_id: string;
  /** 命中的 option id 列表；纯自由输入时为空。 */
  selected_option_ids: string[];
  /** 自由文本补充；可空。 */
  freeform_text: string;
}

/** 复杂度等级。沿用 VotingCard 三色体系：low=approve、medium=neutral、high=oppose。 */
export type ComplexityLevel = 'low' | 'medium' | 'high';

/**
 * 主持人对议题的复杂度判断。会作为 Host Timeline 消息的一种结构化 variant 渲染。
 */
export interface ComplexityAnalysis {
  level: ComplexityLevel;
  /** 1-2 句简短理由，避免大段文字，控制在约 80 字以内。 */
  rationale: string;
  /** 可选的维度分解，比如「技术深度 / 团队影响 / 决策影响」。空则不渲染。 */
  dimensions?: string[];
}

/**
 * 主持人对单个 agent 的派发任务。
 */
export interface DispatchTask {
  /** 目标 agent 的 name（与 AgentInfo.name 对齐）。 */
  agent_name: string;
  /** 该 agent 需要重点回答的子问题。 */
  sub_topic: string;
  /** 期望产出，比如「方案对比表」「踩坑清单」。可空。 */
  expected_output?: string;
}

export type DispatchExecutionMode = 'direct' | 'focused' | 'panel';

/**
 * 主持人的派发计划。会作为 Host Timeline 消息的一种结构化 variant，
 * 同时也是 TopicConfirm 大卡片的关键信息源。
 */
export interface DispatchPlan {
  tasks: DispatchTask[];
  execution_mode?: DispatchExecutionMode;
  selected_agents?: string[];
  expected_final_output?: string;
  /** 派发整体策略说明，可空。 */
  rationale?: string;
  recommended_preset?: string;
}

export interface PresetInfo {
  name: string;
  label: string;
  description: string;
  agents: Array<{ name: string; description: string; model?: string }>;
}

export interface PresetRecommendation {
  recommended: string;
  presets: PresetInfo[];
}

/**
 * Host Timeline 消息的三种 variant。
 * - normal：主持人普通发言（提问/澄清/承上启下）
 * - complexity：复杂度判断结构化卡片
 * - dispatch：派发计划结构化卡片
 *
 * 后端通过 `Message.meta.variant` 路由；缺省视为 `normal`，确保旧消息能正确回放。
 */
export type HostMessageVariant = 'normal' | 'complexity' | 'dispatch';

/**
 * Host 消息的结构化元数据。挂在 `Message.meta` 上随 message 事件一起下发。
 */
export interface HostMessageMeta {
  variant: HostMessageVariant;
  complexity?: ComplexityAnalysis;
  dispatch?: DispatchPlan;
  /** 仅 dispatch variant 用：精炼后的议题文案，如果有的话。 */
  refined_topic?: string;
}

/**
 * 议题精炼完成后的总结，用于驱动 TopicConfirmCard 大卡片。
 * 对应 WS 事件 `topic_refined`。
 */
export interface TopicRefinedPayload {
  original_topic: string;
  refined_topic: string;
  complexity: ComplexityAnalysis;
  dispatch_plan: DispatchPlan;
  execution_mode?: DispatchExecutionMode;
  selected_agents?: string[];
  expected_final_output?: string;
  /** 给后续 discussion 阶段透传的上下文摘要，前端无需展示。 */
  context_summary?: string;
}

/**
 * Brainstorm 阶段的失败/兜底状态。
 *
 * 用于 BrainstormStates 组件路由：
 * - parse_failed：LLM 返回非 JSON，已用原议题继续
 * - skipped：用户主动跳过澄清
 * - timeout：5 分钟无响应，已自动跳过
 * - reconnected：刷新/断网重连后从 localStorage 恢复
 */
export type BrainstormFailureKind =
  | 'parse_failed'
  | 'skipped'
  | 'timeout'
  | 'reconnected';

export interface BrainstormFailureState {
  kind: BrainstormFailureKind;
  /** UI 上展示的简短文案；不传时由组件按 kind 给默认值。 */
  message?: string;
}

// =============================================================================
// Agent 配置设置页（Settings）— 任务 1B
// =============================================================================

/**
 * Model Registry 中一条模型记录（公开视图）。
 *
 * 后端使用 ModelProfilePublic 序列化；不含 api_key/secret/token。
 * env_var_name 是裸名（如 "MIMO_API_KEY"），不是 yaml 里的模板字符串 "${MIMO_API_KEY:-}"（决议 Q1）。
 */
export interface ModelProfile {
  name: string;
  provider: string;
  base_url: string;
  /** 该 provider 下的模型 ID 列表（如 ["GLM-5.1", "Kimi-K2.6"]）。 */
  models: string[];
  /** 裸 env 变量名，仅展示用；前端不能拿到真实 key 值。 */
  env_var_name: string;
  /** 脱敏后的 key 预览，如 sk-a***...b3d；后端未配置对应环境变量时为空。 */
  key_masked?: string;
}

/**
 * Agents Tab 中编辑的草稿。后端使用 AgentConfigPublic 视图。
 *
 * Model Registry ontology 双轨规则（决议 Q2/Q5）：
 * - model 命中 registry → 后端 PUT 时自动清空 inline base_url/api_key 字段，响应携带 sanitized_fields
 * - model 不命中 → 走旧路径，行为不变
 */
export interface AgentDraft {
  name: string;
  description: string;
  /** 引用 ModelProfile.name；旧 agent 也可填裸 model_id 字符串走旧路径。 */
  model: string;
  is_moderator: boolean;
  final_only: boolean;
}

/**
 * Presets Tab 中查看/复制的 preset 草稿。
 */
export interface PresetDraft {
  name: string;
  label: string;
  description: string;
  agents: Array<{ name: string; description: string; model?: string }>;
}

/**
 * Runtime 参数聚合视图（决议 Q5）：yaml schema 不动，前端聚合 4 字段，后端拆分写回。
 */
export interface RuntimeParams {
  max_rounds: number;
  brainstorm_enabled: boolean;
  voting_timeout_s: number;
  /** Synthesizer 调用模型；null = 沿用 discussion 默认；非 null 必须 ∈ ModelProfile.name 集合。 */
  summary_model: string | null;
}

/** Config API GET /api/config 完整响应（脱敏视图）。 */
export interface AppConfigPublic {
  /** 后端 schema 上为可选；缺省视作空数组（决议 Q2：不种子化 registry）。 */
  models?: ModelProfile[];
  agents: AgentDraft[];
  /** 后端 schema 上为可选；缺省视作空数组。 */
  presets?: PresetDraft[];
  runtime: RuntimeParams;
}

/** Config PUT 时的服务端净化报告（决议 Q5）。 */
export interface ConfigSanitizedFields {
  agent_name: string;
  /** 被清空的 inline 字段名（如 base_url、api_key）。 */
  sanitized_fields: string[];
}

/** PUT 失败的错误响应。409=lost-update；422=schema 校验失败。 */
export interface ConfigPutError {
  status: 409 | 422;
  detail: string;
  /** 422 时携带，指出非法字段。 */
  field?: string;
}

// =============================================================================
// 事后总结仪表盘（Discussion Summary）— 任务 2B
// =============================================================================

/**
 * Synthesizer 提取的单条关键论点（决议 Q6）。
 */
export interface KeyPoint {
  agent_name: string;
  text: string;
}

/**
 * 事后总结仪表盘上一个 agent 的卡片数据（决议 Q6：不含 stance/confidence/source）。
 *
 * stance/confidence/source 由前端在 voting 阶段完成后 merge votingResult.votes by name 注入，
 * 不在 Synthesizer 输出内。
 */
export interface AgentParticipant {
  name: string;
  role: string;
  /** 底层 model_id 字符串，用于头像横条角标展示。 */
  model: string;
  is_moderator: boolean;
  message_count: number;
  /** Synthesizer 为该 agent 提取的 3-5 条关键论点。 */
  key_points: string[];
}

/** Synthesizer 两段式降级失败时的标记（plan §5 R7）。 */
export type DegradedReason = 'json_parse_failed' | 'synthesis_truncated';

/**
 * 事后总结仪表盘的核心数据结构。对应 WS 事件 `discussion_summary`（决议 Q6）。
 */
export interface DiscussionSummary {
  /** 后端默认 2；缺省时前端视作 2。 */
  schema_version?: number;
  participants: AgentParticipant[];
  /** ≤300 字提炼结论；degraded=true 时 ≤500 字截断 markdown。 */
  distilled_conclusion: string;
  /** true = Synthesizer JSON 解析失败，已走两段式降级。前端展示 DegradedBanner（默认 false）。 */
  degraded?: boolean;
  degraded_reason?: DegradedReason | null;
}

/**
 * Voting 阶段后注入的 stance/confidence/source 增量信息。
 *
 * 前端按 agent name 匹配 votingResult.votes，叠加到 AgentParticipant 卡片上。
 * stance: support | oppose | neutral | timeout | error
 * source: valid | timeout | error（决议 Q3：confidence 仍是 float 默认 0.0，仅作展示数值）
 */
export interface AgentVoteOverlay {
  agent_name: string;
  stance: 'support' | 'oppose' | 'neutral' | 'timeout' | 'error';
  /** 来自 VoteResult.confidence；timeout/error 通常为 0.0（仅展示用，不做判据）。 */
  confidence: number;
  /** 来自 VoteResult.source；判定有效性的唯一字段。 */
  source: 'valid' | 'timeout' | 'error';
  reason: string;
}
