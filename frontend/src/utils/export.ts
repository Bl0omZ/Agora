import type { AgentSystemBlueprint, Message, VotingResult, DiscussionSummary, AgentParticipant } from '../types';
import { PHASE_LABELS } from '../constants';
import { displayAgentName } from './modelName';

export function exportAsMarkdown(
  topic: string,
  messages: Message[],
  votingResult: VotingResult | null,
): string {
  const lines: string[] = [
    `# ${topic}`,
    '',
    `> 导出时间：${new Date().toLocaleString('zh-CN')}`,
    '',
  ];

  let lastPhase = '';
  for (const msg of messages) {
    if (msg.phase !== lastPhase) {
      lines.push('', `## ${PHASE_LABELS[msg.phase] ?? msg.phase}`, '');
      lastPhase = msg.phase;
    }
    lines.push(`### ${displayAgentName(msg.name)}`, '', msg.content, '');
  }

  if (votingResult) {
    lines.push('## 方案评审', '');
    for (const vote of votingResult.votes) {
      lines.push(`- **${displayAgentName(vote.agent_name)}**：${vote.stance}（置信度 ${(vote.confidence * 100).toFixed(0)}%）`);
      lines.push(`  ${vote.reason}`);
    }
    lines.push('', `**结论**：${votingResult.conclusion}`);
  }

  return lines.join('\n');
}

export function downloadMarkdown(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function printAsPdf(): void {
  window.print();
}

export async function captureScreenshot(element: HTMLElement): Promise<void> {
  const html2canvas = (await import('html2canvas')).default;
  const canvas = await html2canvas(element, { scale: 2, useCORS: true });
  const url = canvas.toDataURL('image/png');
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `discussion-${Date.now()}.png`;
  anchor.click();
}

export async function exportBlueprint(
  blueprint: AgentSystemBlueprint,
  format: 'markdown' | 'json' | 'yaml' | 'prompt_pack',
): Promise<void> {
  const res = await fetch('/api/blueprint/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ blueprint, format }),
  });
  if (!res.ok) {
    throw new Error(`Export failed: ${res.status}`);
  }
  const data = await res.json();
  for (const file of data.files ?? []) {
    const blob = new Blob([file.content], { type: file.mime_type ?? 'text/plain' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = file.filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }
}

export async function exportSolution(
  topic: string,
  summary: DiscussionSummary | null,
  votingResult: VotingResult | null,
): Promise<void> {
  const participants = (summary?.participants ?? []).map((p: AgentParticipant) => ({
    name: p.name,
    model: p.model,
    role: p.role,
  }));
  const res = await fetch('/api/solution/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic,
      distilled_conclusion: summary?.distilled_conclusion ?? '',
      voting_conclusion: votingResult?.conclusion ?? '',
      participants,
      votes: votingResult?.votes ?? [],
    }),
  });
  if (!res.ok) throw new Error(`导出失败: ${res.status}`);
  const data = await res.json();
  const blob = new Blob([data.content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = data.filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
