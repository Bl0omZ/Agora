import type { Message, VotingResult } from '../types';
import { PHASE_LABELS } from '../constants';

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
    lines.push(`### ${msg.name}`, '', msg.content, '');
  }

  if (votingResult) {
    lines.push('## 方案评审', '');
    for (const vote of votingResult.votes) {
      lines.push(`- **${vote.agent_name}**：${vote.stance}（置信度 ${(vote.confidence * 100).toFixed(0)}%）`);
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
