import { marked } from 'marked';

marked.setOptions({ breaks: true, gfm: true });

export function renderMarkdown(text: string): string {
  if (!text) return '';
  try {
    return marked.parse(text) as string;
  } catch {
    return text;
  }
}
