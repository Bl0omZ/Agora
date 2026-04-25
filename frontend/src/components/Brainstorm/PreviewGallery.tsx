import { useState } from 'react';
import type {
  AgentInfo,
  AgentState,
  BrainstormFailureKind,
  BrainstormQuestion,
  HostMessageMeta,
  Message,
  TopicRefinedPayload,
} from '../../types';
import { AgentStatusPanel } from '../Progress/AgentStatusPanel';
import { HostMessage } from '../Timeline/HostMessage';
import { BrainstormPanel } from './BrainstormPanel';
import { TopicConfirmCard } from './TopicConfirmCard';
import {
  BrainstormLoadingPlaceholder,
  BrainstormNotice,
  BrainstormSkipConfirm,
} from './BrainstormStates';
import styles from './PreviewGallery.module.css';

// =============================================================================
// Mock 数据 —— 真实业务上线后由后端 WS 事件填充
// =============================================================================

const MOCK_AGENTS: AgentInfo[] = [
  {
    name: 'Host',
    description: '主持人 · 议题精炼与派发',
    model: 'glm-4.6',
    final_only: false,
    is_moderator: true,
  },
  {
    name: 'Architect',
    description: '架构师',
    model: 'gpt-4o',
    final_only: false,
  },
  {
    name: 'Pragmatist',
    description: '务实派',
    model: 'qwen-max',
    final_only: false,
  },
  {
    name: 'Challenger',
    description: '挑战者',
    model: 'claude-sonnet-4',
    final_only: false,
  },
  {
    name: 'Synthesizer',
    description: '总结者',
    model: 'gpt-4o',
    final_only: true,
  },
];

const MOCK_AGENT_STATES_BRAINSTORMING: Record<string, AgentState> = {
  Host: { name: 'Host', status: 'thinking', speakCount: 1 },
  Architect: { name: 'Architect', status: 'idle', speakCount: 0 },
  Pragmatist: { name: 'Pragmatist', status: 'idle', speakCount: 0 },
  Challenger: { name: 'Challenger', status: 'idle', speakCount: 0 },
  Synthesizer: { name: 'Synthesizer', status: 'idle', speakCount: 0 },
};

const MOCK_AGENT_STATES_DISPATCHED: Record<string, AgentState> = {
  Host: { name: 'Host', status: 'spoken', speakCount: 3 },
  Architect: { name: 'Architect', status: 'thinking', speakCount: 0 },
  Pragmatist: { name: 'Pragmatist', status: 'thinking', speakCount: 0 },
  Challenger: { name: 'Challenger', status: 'thinking', speakCount: 0 },
  Synthesizer: { name: 'Synthesizer', status: 'idle', speakCount: 0 },
};

const MOCK_QUESTION: BrainstormQuestion = {
  id: 'q1',
  round: 2,
  max_rounds: 5,
  question:
    '为了帮你更精准地讨论这个话题，我想先确认两件事：你们目前的团队规模大致是多少？以及，是否已经有线上业务对延迟比较敏感？',
  options: [
    { id: 'small', label: '小团队（<10 人）' },
    { id: 'medium', label: '中型团队（10-50 人）' },
    { id: 'large', label: '大型团队（>50 人）' },
    { id: 'latency-yes', label: '有低延迟业务' },
    { id: 'latency-no', label: '没有强延迟需求' },
  ],
  allow_multiple: true,
  allow_freeform: true,
};

const baseTimestamp = Date.now() - 60_000;

const MOCK_HOST_NORMAL: Message = {
  id: 1,
  name: 'Host',
  content:
    '在我们正式开始之前，我想先帮你把这个议题打磨得更具体一点。这样大家就能更聚焦地表达观点，避免讨论变得太泛。',
  phase: 'brainstorming',
  role: 'assistant',
  timestamp: baseTimestamp,
};

const MOCK_HOST_COMPLEXITY: Message = {
  id: 2,
  name: 'Host',
  content: '复杂度判断',
  phase: 'brainstorming',
  role: 'assistant',
  timestamp: baseTimestamp + 30_000,
};

const MOCK_COMPLEXITY_META: HostMessageMeta = {
  variant: 'complexity',
  complexity: {
    level: 'medium',
    rationale:
      '这是一个典型的「架构选型 vs 团队成本」权衡题：技术维度有标准答案，但落地成本高度依赖团队现状。建议讨论 2-3 轮即可收敛。',
    dimensions: ['技术深度 中', '团队影响 高', '决策可逆性 中'],
  },
};

const MOCK_HOST_DISPATCH: Message = {
  id: 3,
  name: 'Host',
  content: '派发计划',
  phase: 'brainstorming',
  role: 'assistant',
  timestamp: baseTimestamp + 60_000,
};

const MOCK_DISPATCH_META: HostMessageMeta = {
  variant: 'dispatch',
  refined_topic:
    '针对中型 SaaS 后端（5 个微服务、<50 人团队），评估 GraphQL Federation vs REST + BFF 在团队学习成本、性能、客户端开发效率三个维度的权衡。',
  dispatch: {
    tasks: [
      {
        agent_name: 'Architect',
        sub_topic: '从长期可扩展性角度分析 Federation 模式的优势与边界',
        expected_output: '架构对比表',
      },
      {
        agent_name: 'Pragmatist',
        sub_topic: '团队学习曲线 + 落地成本 + 现有 REST 资产迁移代价',
        expected_output: '落地路线图',
      },
      {
        agent_name: 'Challenger',
        sub_topic: 'REST + BFF 的反方论据，以及 GraphQL 在中型团队常见的隐藏陷阱',
        expected_output: '风险清单',
      },
    ],
    rationale: '让三位 agent 形成「正方 / 中立落地派 / 反方」的三角张力，有助于讨论收敛。',
  },
};

const MOCK_TOPIC_REFINED: TopicRefinedPayload = {
  original_topic: '我们应该用 GraphQL 还是 REST？',
  refined_topic: MOCK_DISPATCH_META.refined_topic!,
  complexity: MOCK_COMPLEXITY_META.complexity!,
  dispatch_plan: MOCK_DISPATCH_META.dispatch!,
  context_summary: '团队规模 <50；存在低延迟核心链路；当前以 REST 为主。',
};

// =============================================================================
// PreviewGallery 组件
// =============================================================================

const FAILURE_KINDS: BrainstormFailureKind[] = [
  'parse_failed',
  'skipped',
  'timeout',
  'reconnected',
];

/**
 * 仅供开发预览。通过 `?preview=brainstorm` 进入。
 * 不连后端、不做持久化、所有交互回调都打到 console。
 */
export function PreviewGallery() {
  const [agentMode, setAgentMode] = useState<'brainstorming' | 'dispatched'>(
    'brainstorming',
  );
  const [skipModalOpen, setSkipModalOpen] = useState(false);
  const [activeFailures, setActiveFailures] = useState<BrainstormFailureKind[]>([
    'parse_failed',
    'reconnected',
  ]);

  const toggleFailure = (kind: BrainstormFailureKind) => {
    setActiveFailures((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind],
    );
  };

  const agentStates =
    agentMode === 'brainstorming'
      ? MOCK_AGENT_STATES_BRAINSTORMING
      : MOCK_AGENT_STATES_DISPATCHED;

  return (
    <div className={styles.gallery}>
      <header className={styles.galleryHeader}>
        <h1 className={styles.galleryTitle}>Brainstorming UI · 组件预览</h1>
        <div className={styles.gallerySubtitle}>
          dev only · 通过 <code>?preview=brainstorm</code> 进入 · 所有交互回调走 console
        </div>
      </header>

      {/* === Section 1: AgentStatusPanel ============================== */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>1. AgentStatusPanel · Host amber + thinking 派发</h2>
          <span className={styles.sectionDesc}>
            主持人卡片走 amber + 主持人 badge + 模型名；切换状态查看「主持人思考」vs「派发后 agent 思考」
          </span>
        </div>
        <div className={styles.toggleRow}>
          <button
            type="button"
            className={`${styles.toggleButton} ${agentMode === 'brainstorming' ? styles.active : ''}`}
            onClick={() => setAgentMode('brainstorming')}
          >
            brainstorming · Host thinking
          </button>
          <button
            type="button"
            className={`${styles.toggleButton} ${agentMode === 'dispatched' ? styles.active : ''}`}
            onClick={() => setAgentMode('dispatched')}
          >
            dispatched · 3 个 agent 同时思考
          </button>
        </div>
        <AgentStatusPanel agents={MOCK_AGENTS} agentStates={agentStates} />
      </section>

      <div className={styles.divider} />

      {/* === Section 2: HostMessage 三 variant ========================== */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>2. Timeline · Host 消息三 variant</h2>
          <span className={styles.sectionDesc}>
            normal / complexity / dispatch · 同一个 message 流，meta.variant 路由
          </span>
        </div>
        <div className={styles.timelineMock}>
          <HostMessage message={MOCK_HOST_NORMAL} meta={{ variant: 'normal' }} />
          <HostMessage message={MOCK_HOST_COMPLEXITY} meta={MOCK_COMPLEXITY_META} />
          <HostMessage message={MOCK_HOST_DISPATCH} meta={MOCK_DISPATCH_META} />
        </div>
      </section>

      <div className={styles.divider} />

      {/* === Section 3: BrainstormPanel =============================== */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>3. BrainstormPanel · 底部交互卡</h2>
          <span className={styles.sectionDesc}>
            主持人发问 + 多选 chip + 自由输入 + 跳过 link · 提交按钮按需可用
          </span>
        </div>
        <BrainstormPanel
          question={MOCK_QUESTION}
          onSubmit={(answer) => console.log('[preview] submit answer →', answer)}
          onSkip={() => setSkipModalOpen(true)}
        />
      </section>

      <div className={styles.divider} />

      {/* === Section 4: TopicConfirmCard ============================== */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>4. TopicConfirmCard · 进入讨论前的确认</h2>
          <span className={styles.sectionDesc}>
            原议题 → 精炼议题 + 复杂度 chip + 派发计划 + 「开始讨论 →」CTA
          </span>
        </div>
        <TopicConfirmCard
          payload={MOCK_TOPIC_REFINED}
          onConfirm={() => console.log('[preview] confirm topic, enter discussion')}
          onRefine={() => console.log('[preview] refine again')}
        />
      </section>

      <div className={styles.divider} />

      {/* === Section 5: BrainstormStates ============================= */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>5. BrainstormStates · 失败 / 兜底 / 等待</h2>
          <span className={styles.sectionDesc}>
            点 chip 切换 notice 显示 · 跳过 modal 在第 3 节触发
          </span>
        </div>
        <div className={styles.toggleRow}>
          {FAILURE_KINDS.map((k) => (
            <button
              key={k}
              type="button"
              className={`${styles.toggleButton} ${activeFailures.includes(k) ? styles.active : ''}`}
              onClick={() => toggleFailure(k)}
            >
              {k}
            </button>
          ))}
        </div>
        {activeFailures.map((kind) => (
          <BrainstormNotice
            key={kind}
            state={{ kind }}
            onDismiss={() => toggleFailure(kind)}
          />
        ))}
        <BrainstormLoadingPlaceholder />
      </section>

      {/* === Modal （由 BrainstormPanel 跳过触发）======================= */}
      <BrainstormSkipConfirm
        open={skipModalOpen}
        onCancel={() => setSkipModalOpen(false)}
        onConfirm={() => {
          console.log('[preview] confirmed skip');
          setSkipModalOpen(false);
        }}
      />
    </div>
  );
}
