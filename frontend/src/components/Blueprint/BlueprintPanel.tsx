import { useState } from 'react';
import type { AgentSystemBlueprint, BlueprintExportFormat } from '../../types';
import styles from './BlueprintPanel.module.css';

const AGENT_DISPLAY_NAMES: Record<string, string> = {
  Architect: '架构师',
  Pragmatist: '务实派',
  Challenger: '挑战者',
  Evaluator: '评估师',
  RequirementsAnalyst: '需求分析师',
  DomainExpert: '领域专家',
  ProcessDesigner: '流程设计师',
  RootCauseAnalyst: '根因分析师',
};

function agentDisplayName(name: string): string {
  return AGENT_DISPLAY_NAMES[name] ?? name;
}

function riskStyle(severity: string): string {
  const v = severity.toLowerCase();
  if (v === 'high' || v === '高') return styles.sevHigh;
  if (v === 'medium' || v === '中') return styles.sevMed;
  return styles.sevLow;
}

interface BlueprintPanelProps {
  blueprint: AgentSystemBlueprint;
  warnings: string[];
  onExport: (format: BlueprintExportFormat) => void;
}

export function BlueprintPanel({ blueprint, warnings, onExport }: BlueprintPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const agentCount = blueprint.agents.length;
  const stepCount = blueprint.workflow.steps.length;
  const riskCount = blueprint.risks.length;

  return (
    <div className={styles.card}>
      <button
        type="button"
        className={styles.header}
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
      >
        <div className={styles.headerLeft}>
          <span className={styles.kicker}>讨论概览</span>
          <h3 className={styles.title}>{blueprint.name}</h3>
          <div className={styles.meta}>
            <span>{agentCount} 位参与者</span>
            <span className={styles.dot} />
            <span>{stepCount} 个步骤</span>
            {riskCount > 0 && (
              <>
                <span className={styles.dot} />
                <span>{riskCount} 项风险</span>
              </>
            )}
          </div>
        </div>
        <span className={`${styles.chevron} ${expanded ? styles.chevronOpen : ''}`}>
          &#9662;
        </span>
      </button>

      <div className={styles.problem}>
        <p className={expanded ? '' : styles.clamp}>{blueprint.problem_statement}</p>
      </div>

      {warnings.length > 0 && (
        <div className={styles.warn}>
          <span className={styles.warnIcon}>ℹ️</span>
          <div className={styles.warnBody}>
            {warnings.map((w, i) => <p key={i}>{w}</p>)}
          </div>
        </div>
      )}

      {expanded && (
        <div className={styles.body}>
          <div className={styles.section}>
            <h4 className={styles.sectionTitle}>参与 Agent</h4>
            <div className={styles.agents}>
              {blueprint.agents.map(a => (
                <div key={a.name} className={styles.agentCard}>
                  <strong>{agentDisplayName(a.name)}</strong>
                  <span className={styles.agentRole}>{a.role}</span>
                </div>
              ))}
            </div>
          </div>

          <div className={styles.section}>
            <h4 className={styles.sectionTitle}>讨论流程</h4>
            <div className={styles.flow}>
              {blueprint.workflow.steps.map((s, i) => (
                <div key={s.id} className={styles.step}>
                  <span className={styles.stepNum}>{i + 1}</span>
                  <div className={styles.stepBody}>
                    <div className={styles.stepHead}>
                      <strong>{s.name}</strong>
                      <span className={styles.stepOwner}>{agentDisplayName(s.owner_agent)}</span>
                    </div>
                    {s.output && <p className={styles.stepOutput}>{s.output}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {riskCount > 0 && (
            <div className={styles.section}>
              <h4 className={styles.sectionTitle}>潜在风险</h4>
              <div className={styles.risks}>
                {blueprint.risks.map((r, i) => (
                  <div key={i} className={styles.risk}>
                    <span className={`${styles.severity} ${riskStyle(r.severity)}`}>
                      {r.severity}
                    </span>
                    <div>
                      <p className={styles.riskText}>{r.risk}</p>
                      {r.mitigation && <p className={styles.riskMit}>{r.mitigation}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className={styles.exports}>
            <span className={styles.exportLabel}>导出</span>
            <div className={styles.exportBtns}>
              <button type="button" onClick={() => onExport('markdown')}>Markdown</button>
              <button type="button" onClick={() => onExport('json')}>JSON</button>
              <button type="button" onClick={() => onExport('yaml')}>YAML</button>
              <button type="button" onClick={() => onExport('prompt_pack')}>Prompt Pack</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}