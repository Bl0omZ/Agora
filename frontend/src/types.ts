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
