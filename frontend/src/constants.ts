export interface RoleStyle {
  label: string;
  initial: string;
  color: string;
  background: string;
  ink: string;
}

export const ROLE_CONFIG: Record<string, RoleStyle> = {
  Host: {
    label: '主持人',
    initial: 'H',
    color: 'var(--role-host)',
    background: 'var(--role-host-bg)',
    ink: 'var(--role-host-ink)',
  },
  Architect: {
    label: '架构师',
    initial: 'A',
    color: 'var(--role-architect)',
    background: 'var(--role-architect-bg)',
    ink: 'var(--role-architect-ink)',
  },
  Pragmatist: {
    label: '务实派',
    initial: 'P',
    color: 'var(--role-pragmatist)',
    background: 'var(--role-pragmatist-bg)',
    ink: 'var(--role-pragmatist-ink)',
  },
  Challenger: {
    label: '挑战者',
    initial: 'C',
    color: 'var(--role-challenger)',
    background: 'var(--role-challenger-bg)',
    ink: 'var(--role-challenger-ink)',
  },
  Synthesizer: {
    label: '总结者',
    initial: 'S',
    color: 'var(--role-synthesizer)',
    background: 'var(--role-synthesizer-bg)',
    ink: 'var(--role-synthesizer-ink)',
  },
};

export const DEFAULT_ROLE_STYLE: RoleStyle = {
  label: 'Unknown',
  initial: '?',
  color: 'var(--ink-muted)',
  background: 'var(--bg-input)',
  ink: 'var(--ink-secondary)',
};

export function getRoleStyle(name: string): RoleStyle {
  return ROLE_CONFIG[name] ?? { ...DEFAULT_ROLE_STYLE, label: name, initial: name.charAt(0) };
}

export const PHASE_LABELS: Record<string, string> = {
  brainstorming: '议题精炼',
  discussion: '讨论阶段',
  synthesis: '最终方案',
  blueprint: 'Agent 系统蓝图',
  voting: '方案评审',
  followup: '后续交互',
  followup_round: '追问讨论',
};

export const PHASE_ORDER: string[] = ['brainstorming', 'discussion', 'synthesis', 'blueprint', 'voting', 'followup'];

export const SCHEMA_VERSION = 2;
export const SESSION_INDEX_KEY = 'ad-sessions-index';
export const SESSION_PREFIX = 'ad-session-';
export const MAX_SESSIONS = 50;
