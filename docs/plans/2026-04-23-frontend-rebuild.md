# Agent Discussion 前端重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent Discussion 前端从单文件 inline React + Babel 重构为 Vite + React + TypeScript 工程化方案，新增进度感知、Agent 配置、报告浏览、导出、日志等功能，并遵循 Huashu Design 美学规范。

**Architecture:** 前端使用 Vite 6 构建，React 18 + TypeScript 组件化开发，CSS Modules 样式隔离。后端 Python FastAPI 保持不变，新增若干 REST API 和 WebSocket 事件支持新功能。开发时 Vite 代理 WebSocket/API 到后端 8001 端口，生产时 Python 直接 serve `dist/` 静态文件。

**Tech Stack:** Vite 6 · React 18 · TypeScript · CSS Modules · marked.js · html2canvas · FastAPI (Python, 不变)

---

## 文件结构

```
agent-discussion/frontend/
├── index.html                    # Vite 入口 HTML
├── package.json                  # 依赖与脚本
├── tsconfig.json                 # TypeScript 配置
├── vite.config.ts                # Vite 配置（WebSocket 代理）
├── src/
│   ├── main.tsx                  # React 挂载点
│   ├── App.tsx                   # 主布局：Sidebar + Main
│   ├── App.module.css            # 主布局样式
│   ├── types.ts                  # 全局 TypeScript 类型定义
│   ├── constants.ts              # 角色配置、阶段标签等常量
│   ├── styles/
│   │   ├── variables.css         # CSS 变量（Huashu Design 色板）
│   │   ├── reset.css             # 全局重置
│   │   └── markdown.css          # Markdown 内容样式
│   ├── hooks/
│   │   ├── useWebSocket.ts       # WebSocket 连接管理
│   │   └── useSession.ts         # 会话持久化（localStorage + API 双写）
│   ├── utils/
│   │   ├── markdown.ts           # Markdown 渲染工具
│   │   ├── session.ts            # SessionManager（localStorage CRUD）
│   │   ├── time.ts               # 时间格式化工具
│   │   └── export.ts             # 导出工具（Markdown/PDF/截图）
│   └── components/
│       ├── Sidebar/
│       │   ├── Sidebar.tsx       # 侧边栏容器
│       │   ├── Sidebar.module.css
│       │   ├── SessionList.tsx   # 历史会话列表
│       │   ├── FilterPanel.tsx   # 角色 + 阶段筛选面板
│       │   └── ReportList.tsx    # 历史报告列表
│       ├── TopBar/
│       │   ├── TopBar.tsx        # 顶栏：话题 + 状态 + 操作按钮
│       │   └── TopBar.module.css
│       ├── Progress/
│       │   ├── ProgressBar.tsx   # 阶段进度条（讨论→总结→投票→追问）
│       │   ├── ProgressBar.module.css
│       │   ├── AgentStatusPanel.tsx  # Agent 实时状态面板
│       │   └── AgentStatusPanel.module.css
│       ├── Timeline/
│       │   ├── MessageBubble.tsx     # 消息气泡
│       │   ├── MessageBubble.module.css
│       │   ├── PhaseDivider.tsx      # 阶段分隔线
│       │   ├── VotingCard.tsx        # 投票结果卡片
│       │   ├── VotingCard.module.css
│       │   └── TypingIndicator.tsx   # 打字中指示器
│       ├── Settings/
│       │   ├── ConfigPanel.tsx       # 讨论配置面板（轮数/模型）
│       │   └── ConfigPanel.module.css
│       ├── Report/
│       │   ├── ReportViewer.tsx      # 报告 Markdown 预览
│       │   └── ReportViewer.module.css
│       ├── Welcome/
│       │   ├── Welcome.tsx           # 欢迎页
│       │   └── Welcome.module.css
│       ├── InputBar/
│       │   ├── InputBar.tsx          # 底部输入栏
│       │   └── InputBar.module.css
│       ├── LogPanel/
│       │   ├── LogPanel.tsx          # Pipeline 日志面板
│       │   └── LogPanel.module.css
│       └── common/
│           ├── RoleBadge.tsx         # 角色徽章
│           ├── ConnectionDot.tsx     # 连接状态指示灯
│           └── common.module.css
└── dist/                             # build 产出（gitignore）
```

**后端修改文件：**
- 修改: `agent-discussion/src/web_server.py` — 新增 REST API + WebSocket 事件
- 修改: `agent-discussion/src/models.py` — 无需修改（现有模型已足够）

---

## Task 1: 初始化 Vite + React + TypeScript 工程

**Files:**
- Create: `agent-discussion/frontend/package.json`
- Create: `agent-discussion/frontend/tsconfig.json`
- Create: `agent-discussion/frontend/vite.config.ts`
- Create: `agent-discussion/frontend/index.html`
- Create: `agent-discussion/frontend/src/main.tsx`
- Create: `agent-discussion/frontend/.gitignore`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "agent-discussion-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "marked": "^15.0.0",
    "html2canvas": "^1.4.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "~5.6.2",
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 2: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: 创建 vite.config.ts**

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/ws': {
        target: 'http://localhost:8001',
        ws: true,
      },
      '/api': {
        target: 'http://localhost:8001',
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
```

- [ ] **Step 4: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Agent Discussion</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;0,6..72,700;1,6..72,400&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 src/main.tsx**

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/reset.css';
import './styles/variables.css';
import './styles/markdown.css';
import { App } from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 6: 创建 .gitignore**

```
node_modules
dist
*.local
```

- [ ] **Step 7: 安装依赖并验证**

```bash
cd agent-discussion/frontend && npm install
npm run dev
```

Expected: Vite 启动成功，浏览器打开 `http://localhost:5173` 显示空白页（尚无 App 组件）。

- [ ] **Step 8: Commit**

```bash
git add agent-discussion/frontend/
git commit -m "feat(frontend): init Vite + React + TypeScript project"
```

---

## Task 2: 设计系统 — CSS 变量与全局样式

**Files:**
- Create: `agent-discussion/frontend/src/styles/reset.css`
- Create: `agent-discussion/frontend/src/styles/variables.css`
- Create: `agent-discussion/frontend/src/styles/markdown.css`

- [ ] **Step 1: 创建 reset.css**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, #root {
  height: 100%;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-medium); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--ink-muted); }

button { cursor: pointer; }
input, button, textarea { font: inherit; }
a { color: inherit; text-decoration: none; }
```

- [ ] **Step 2: 创建 variables.css — Huashu Design 色板**

设计哲学：衬线 display（Newsreader）+ 无衬线 body（DM Sans）配对。暖米色底 + 赤土橙单一 accent 贯穿。减少容器层级，让内容呼吸。

```css
:root {
  /* --- Surface --- */
  --bg-page: #FAF9F7;
  --bg-sidebar: #F3F2EE;
  --bg-card: #FFFFFF;
  --bg-input: #F3F2EE;
  --bg-hover: #EEECEA;
  --bg-active: #E8E6E2;

  /* --- Ink --- */
  --ink-primary: #1A1A19;
  --ink-secondary: #555550;
  --ink-muted: #9C9B96;
  --ink-inverse: #FAFAF9;

  /* --- Border --- */
  --border-light: #E8E6E2;
  --border-medium: #DAD8D3;

  /* --- Accent (赤土橙 — 全场唯一 accent) --- */
  --accent: #C04A1A;
  --accent-soft: #F0DDD4;
  --accent-ink: #8B3514;

  /* --- Role colors — 低饱和度区分，不抢 accent --- */
  --role-host: #B0A090;
  --role-host-bg: #F5F0EB;
  --role-host-ink: #6B5D4F;
  --role-architect: #8BA4B8;
  --role-architect-bg: #EDF2F7;
  --role-architect-ink: #3D5A73;
  --role-pragmatist: #94A87A;
  --role-pragmatist-bg: #EFF3E8;
  --role-pragmatist-ink: #4A5A34;
  --role-challenger: #C4A462;
  --role-challenger-bg: #F7F1E3;
  --role-challenger-ink: #7A6320;
  --role-synthesizer: #9B8EB0;
  --role-synthesizer-bg: #F0ECF5;
  --role-synthesizer-ink: #5A4970;

  /* --- Typography --- */
  --font-display: 'Newsreader', 'Georgia', serif;
  --font-body: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;

  /* --- Spacing --- */
  --radius-small: 3px;
  --radius-medium: 6px;
  --radius-large: 10px;

  /* --- Shadow --- */
  --shadow-soft: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-medium: 0 2px 8px rgba(0,0,0,0.06);
  --shadow-elevated: 0 8px 24px rgba(0,0,0,0.08);
}

body {
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink-primary);
  background: var(--bg-page);
}
```

- [ ] **Step 3: 创建 markdown.css**

```css
.markdown-content h1,
.markdown-content h2,
.markdown-content h3 {
  font-family: var(--font-display);
  margin-top: 1.2em;
  margin-bottom: 0.4em;
  line-height: 1.3;
  color: var(--ink-primary);
}
.markdown-content h1 { font-size: 1.35em; font-weight: 600; }
.markdown-content h2 { font-size: 1.15em; font-weight: 600; }
.markdown-content h3 { font-size: 1.05em; font-weight: 500; }
.markdown-content p { margin-bottom: 0.7em; }
.markdown-content ul,
.markdown-content ol { margin-left: 1.4em; margin-bottom: 0.7em; }
.markdown-content li { margin-bottom: 0.2em; }

.markdown-content code {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: var(--bg-input);
  padding: 1px 5px;
  border-radius: 3px;
}
.markdown-content pre {
  background: #2C2C2B;
  color: #E6E4E0;
  padding: 14px 18px;
  border-radius: var(--radius-medium);
  overflow-x: auto;
  margin-bottom: 0.8em;
  font-size: 0.85em;
  line-height: 1.5;
}
.markdown-content pre code {
  background: none;
  padding: 0;
  color: inherit;
}
.markdown-content blockquote {
  border-left: 2px solid var(--accent);
  padding-left: 14px;
  color: var(--ink-secondary);
  margin-bottom: 0.7em;
  font-style: italic;
}
.markdown-content table {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 0.8em;
  font-size: 0.92em;
}
.markdown-content th,
.markdown-content td {
  border: 1px solid var(--border-light);
  padding: 6px 10px;
  text-align: left;
}
.markdown-content th {
  background: var(--bg-input);
  font-weight: 600;
}
.markdown-content hr {
  border: none;
  border-top: 1px solid var(--border-light);
  margin: 1.2em 0;
}
.markdown-content strong { font-weight: 600; }
.markdown-content a { color: var(--accent); text-decoration: underline; }
.markdown-content a:hover { color: var(--accent-ink); }
```

- [ ] **Step 4: Commit**

```bash
git add agent-discussion/frontend/src/styles/
git commit -m "feat(frontend): add Huashu Design system CSS variables"
```

---

## Task 3: 类型定义与常量

**Files:**
- Create: `agent-discussion/frontend/src/types.ts`
- Create: `agent-discussion/frontend/src/constants.ts`

- [ ] **Step 1: 创建 types.ts**

```ts
export interface AgentInfo {
  name: string;
  description: string;
  model: string;
  final_only: boolean;
}

export interface Message {
  id: number;
  name: string;
  content: string;
  phase: string;
  role: string;
  timestamp: number;
}

export interface PhaseEvent {
  phase: string;
  label: string;
  timestamp: number;
}

export interface Vote {
  agent_name: string;
  stance: '赞成' | '反对' | '中立';
  reason: string;
  confidence: number;
}

export interface VotingResult {
  votes: Vote[];
  conclusion: string;
}

export type AgentStatus = 'idle' | 'thinking' | 'spoken';

export interface AgentState {
  name: string;
  status: AgentStatus;
  speakCount: number;
}

export type DiscussionPhase = 'idle' | 'discussion' | 'synthesis' | 'voting' | 'followup' | 'done';

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
```

- [ ] **Step 2: 创建 constants.ts**

```ts
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
  discussion: '讨论阶段',
  synthesis: '最终总结',
  voting: '投票阶段',
  followup: '后续交互',
  followup_round: '追问讨论',
};

export const PHASE_ORDER: string[] = ['discussion', 'synthesis', 'voting', 'followup'];

export const SCHEMA_VERSION = 1;
export const SESSION_INDEX_KEY = 'ad-sessions-index';
export const SESSION_PREFIX = 'ad-session-';
export const MAX_SESSIONS = 50;
```

- [ ] **Step 3: Commit**

```bash
git add agent-discussion/frontend/src/types.ts agent-discussion/frontend/src/constants.ts
git commit -m "feat(frontend): add TypeScript types and constants"
```

---

## Task 4: 工具函数

**Files:**
- Create: `agent-discussion/frontend/src/utils/markdown.ts`
- Create: `agent-discussion/frontend/src/utils/time.ts`
- Create: `agent-discussion/frontend/src/utils/session.ts`
- Create: `agent-discussion/frontend/src/utils/export.ts`

- [ ] **Step 1: 创建 markdown.ts**

```ts
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
```

- [ ] **Step 2: 创建 time.ts**

```ts
export function formatRelativeTime(timestamp: number): string {
  const diffSeconds = Math.floor((Date.now() - timestamp) / 1000);
  if (diffSeconds < 60) return '刚刚';
  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} 天前`;
  const date = new Date(timestamp);
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${milliseconds}ms`;
  const seconds = (milliseconds / 1000).toFixed(1);
  return `${seconds}s`;
}
```

- [ ] **Step 3: 创建 session.ts**

```ts
import type { SessionData, SessionIndexEntry } from '../types';
import { SCHEMA_VERSION, SESSION_INDEX_KEY, SESSION_PREFIX, MAX_SESSIONS } from '../constants';

export const SessionManager = {
  listSessions(): SessionIndexEntry[] {
    try {
      const raw = localStorage.getItem(SESSION_INDEX_KEY);
      if (!raw) return [];
      const sessions: SessionIndexEntry[] = JSON.parse(raw);
      return sessions.sort((a, b) => b.updatedAt - a.updatedAt);
    } catch {
      return [];
    }
  },

  loadSession(id: string): SessionData | null {
    try {
      const raw = localStorage.getItem(`${SESSION_PREFIX}${id}`);
      if (!raw) return null;
      return JSON.parse(raw) as SessionData;
    } catch {
      return null;
    }
  },

  saveSession(data: SessionData): void {
    try {
      localStorage.setItem(`${SESSION_PREFIX}${data.id}`, JSON.stringify(data));
      const index = this.listSessions();
      const existingPosition = index.findIndex(s => s.id === data.id);
      const entry: SessionIndexEntry = {
        id: data.id,
        topic: data.topic,
        messageCount: data.messages.length,
        createdAt: data.createdAt,
        updatedAt: Date.now(),
      };
      if (existingPosition >= 0) {
        index[existingPosition] = entry;
      } else {
        index.push(entry);
      }
      index.sort((a, b) => b.updatedAt - a.updatedAt);
      if (index.length > MAX_SESSIONS) {
        index.slice(MAX_SESSIONS).forEach(s => localStorage.removeItem(`${SESSION_PREFIX}${s.id}`));
      }
      localStorage.setItem(SESSION_INDEX_KEY, JSON.stringify(index.slice(0, MAX_SESSIONS)));
    } catch (error) {
      console.error('Failed to save session:', error);
    }
  },

  deleteSession(id: string): void {
    try {
      localStorage.removeItem(`${SESSION_PREFIX}${id}`);
      const index = this.listSessions().filter(s => s.id !== id);
      localStorage.setItem(SESSION_INDEX_KEY, JSON.stringify(index));
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  },

  createEmptySession(topic: string): SessionData {
    const now = Date.now();
    return {
      schemaVersion: SCHEMA_VERSION,
      id: now.toString(36),
      topic,
      messages: [],
      phases: [],
      votingResult: null,
      logs: [],
      savedPath: null,
      createdAt: now,
      updatedAt: now,
    };
  },
};
```

- [ ] **Step 4: 创建 export.ts**

```ts
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
    lines.push('## 投票结果', '');
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
```

- [ ] **Step 5: Commit**

```bash
git add agent-discussion/frontend/src/utils/
git commit -m "feat(frontend): add utility modules (markdown, time, session, export)"
```

---

## Task 5: WebSocket Hook

**Files:**
- Create: `agent-discussion/frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: 创建 useWebSocket.ts**

这是前端的核心 hook，管理 WebSocket 连接、消息接收、状态分发。新增支持 `round_progress`、`agent_status`、`pipeline_log` 事件。

```ts
import { useState, useEffect, useRef, useCallback } from 'react';
import type {
  AgentInfo, Message, PhaseEvent, VotingResult,
  AgentState, RoundProgress, PipelineLog, DiscussionConfig,
  DiscussionPhase,
} from '../types';

export type ConnectionStatus = 'disconnected' | 'connected' | 'error';

export interface WebSocketState {
  connectionStatus: ConnectionStatus;
  messages: Message[];
  phases: PhaseEvent[];
  agents: AgentInfo[];
  agentStates: Record<string, AgentState>;
  votingResult: VotingResult | null;
  isReady: boolean;
  currentTopic: string;
  currentPhase: DiscussionPhase;
  roundProgress: RoundProgress | null;
  logs: PipelineLog[];
  error: string | null;
  savedPath: string | null;

  send: (data: Record<string, unknown>) => void;
  startDiscussion: (topic: string, config?: DiscussionConfig) => void;
  sendFollowup: (message: string) => void;
  saveReport: (topic: string) => void;
}

export function useWebSocket(): WebSocketState {
  const wsRef = useRef<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [messages, setMessages] = useState<Message[]>([]);
  const [phases, setPhases] = useState<PhaseEvent[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [agentStates, setAgentStates] = useState<Record<string, AgentState>>({});
  const [votingResult, setVotingResult] = useState<VotingResult | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [currentTopic, setCurrentTopic] = useState('');
  const [currentPhase, setCurrentPhase] = useState<DiscussionPhase>('idle');
  const [roundProgress, setRoundProgress] = useState<RoundProgress | null>(null);
  const [logs, setLogs] = useState<PipelineLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [savedPath, setSavedPath] = useState<string | null>(null);
  const messageIdRef = useRef(0);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      setConnectionStatus('connected');
      setError(null);
    };

    socket.onclose = () => {
      setConnectionStatus('disconnected');
      setTimeout(connect, 3000);
    };

    socket.onerror = () => setConnectionStatus('error');

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'agents':
          setAgents(data.agents);
          break;

        case 'phase': {
          const phaseValue = data.phase as string;
          setPhases(prev => [...prev, { phase: phaseValue, label: data.label, timestamp: Date.now() }]);
          if (['discussion', 'synthesis', 'voting', 'followup'].includes(phaseValue)) {
            setCurrentPhase(phaseValue as DiscussionPhase);
          }
          break;
        }

        case 'message': {
          messageIdRef.current += 1;
          const newMsg: Message = {
            id: messageIdRef.current,
            name: data.name,
            content: data.content,
            phase: data.phase,
            role: data.role ?? 'assistant',
            timestamp: Date.now(),
          };
          setMessages(prev => [...prev, newMsg]);
          // Update agent speak count
          setAgentStates(prev => {
            const agentName = data.name;
            const existing = prev[agentName];
            return {
              ...prev,
              [agentName]: {
                name: agentName,
                status: 'spoken',
                speakCount: (existing?.speakCount ?? 0) + 1,
              },
            };
          });
          break;
        }

        case 'voting_result':
          setVotingResult(data as VotingResult);
          break;

        case 'round_progress':
          setRoundProgress({ current: data.current, total: data.total });
          break;

        case 'agent_status':
          setAgentStates(prev => ({
            ...prev,
            [data.name]: {
              name: data.name,
              status: data.status,
              speakCount: prev[data.name]?.speakCount ?? 0,
            },
          }));
          break;

        case 'pipeline_log':
          setLogs(prev => [...prev, {
            phase: data.phase,
            event: data.event,
            timestamp: Date.now(),
            durationMs: data.duration_ms,
            tokens: data.tokens,
            detail: data.detail,
          }]);
          break;

        case 'started':
          setCurrentTopic(data.topic);
          setMessages([]);
          setPhases([]);
          setVotingResult(null);
          setIsReady(false);
          setError(null);
          setSavedPath(null);
          setRoundProgress(null);
          setLogs([]);
          setAgentStates({});
          setCurrentPhase('discussion');
          break;

        case 'ready':
          setIsReady(true);
          setCurrentPhase('done');
          break;

        case 'saved':
          setSavedPath(data.path);
          break;

        case 'error':
          setError(data.message);
          setIsReady(true);
          break;
      }
    };

    wsRef.current = socket;
  }, []);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); };
  }, [connect]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const startDiscussion = useCallback((topic: string, config?: DiscussionConfig) => {
    send({ action: 'start', topic, config: config ?? undefined });
  }, [send]);

  const sendFollowup = useCallback((message: string) => {
    send({ action: 'followup', message });
  }, [send]);

  const saveReport = useCallback((topic: string) => {
    send({ action: 'save', topic });
  }, [send]);

  return {
    connectionStatus, messages, phases, agents, agentStates,
    votingResult, isReady, currentTopic, currentPhase,
    roundProgress, logs, error, savedPath,
    send, startDiscussion, sendFollowup, saveReport,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add agent-discussion/frontend/src/hooks/
git commit -m "feat(frontend): add useWebSocket hook with progress and log support"
```

---

## Task 6: 会话管理 Hook

**Files:**
- Create: `agent-discussion/frontend/src/hooks/useSession.ts`

- [ ] **Step 1: 创建 useSession.ts**

管理 localStorage 双写 + 后端 API 同步 + 历史会话加载。

```ts
import { useState, useEffect, useCallback, useRef } from 'react';
import type { SessionData, SessionIndexEntry, Message, PhaseEvent, VotingResult, PipelineLog } from '../types';
import { SessionManager } from '../utils/session';

interface UseSessionReturn {
  sessions: SessionIndexEntry[];
  currentSessionId: string | null;
  isHistoryMode: boolean;
  createSession: (topic: string) => string;
  updateSessionData: (partial: {
    messages?: Message[];
    phases?: PhaseEvent[];
    votingResult?: VotingResult | null;
    logs?: PipelineLog[];
    savedPath?: string | null;
  }) => void;
  loadHistorySession: (id: string) => SessionData | null;
  startNewSession: () => void;
  deleteSession: (id: string) => void;
  syncToServer: (sessionData: SessionData) => Promise<void>;
}

export function useSession(): UseSessionReturn {
  const [sessions, setSessions] = useState<SessionIndexEntry[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isHistoryMode, setIsHistoryMode] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setSessions(SessionManager.listSessions());
  }, []);

  const refreshIndex = useCallback(() => {
    setSessions(SessionManager.listSessions());
  }, []);

  const createSession = useCallback((topic: string): string => {
    const newSession = SessionManager.createEmptySession(topic);
    SessionManager.saveSession(newSession);
    setCurrentSessionId(newSession.id);
    setIsHistoryMode(false);
    refreshIndex();
    return newSession.id;
  }, [refreshIndex]);

  const updateSessionData = useCallback((partial: {
    messages?: Message[];
    phases?: PhaseEvent[];
    votingResult?: VotingResult | null;
    logs?: PipelineLog[];
    savedPath?: string | null;
  }) => {
    if (!currentSessionId || isHistoryMode) return;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      const existing = SessionManager.loadSession(currentSessionId);
      if (!existing) return;
      const updated: SessionData = {
        ...existing,
        ...(partial.messages !== undefined && { messages: partial.messages }),
        ...(partial.phases !== undefined && { phases: partial.phases }),
        ...(partial.votingResult !== undefined && { votingResult: partial.votingResult }),
        ...(partial.logs !== undefined && { logs: partial.logs }),
        ...(partial.savedPath !== undefined && { savedPath: partial.savedPath }),
        updatedAt: Date.now(),
      };
      SessionManager.saveSession(updated);
      refreshIndex();
    }, 500);
  }, [currentSessionId, isHistoryMode, refreshIndex]);

  const loadHistorySession = useCallback((id: string): SessionData | null => {
    const data = SessionManager.loadSession(id);
    if (data) {
      setCurrentSessionId(id);
      setIsHistoryMode(true);
    }
    return data;
  }, []);

  const startNewSession = useCallback(() => {
    setCurrentSessionId(null);
    setIsHistoryMode(false);
  }, []);

  const deleteSession = useCallback((id: string) => {
    SessionManager.deleteSession(id);
    refreshIndex();
    if (currentSessionId === id) {
      setCurrentSessionId(null);
      setIsHistoryMode(false);
    }
  }, [currentSessionId, refreshIndex]);

  const syncToServer = useCallback(async (sessionData: SessionData) => {
    try {
      await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sessionData),
      });
    } catch (error) {
      console.error('Failed to sync session to server:', error);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  return {
    sessions, currentSessionId, isHistoryMode,
    createSession, updateSessionData, loadHistorySession,
    startNewSession, deleteSession, syncToServer,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add agent-discussion/frontend/src/hooks/useSession.ts
git commit -m "feat(frontend): add useSession hook with localStorage + API dual-write"
```

---

## Task 7: 通用小组件（RoleBadge, ConnectionDot）

**Files:**
- Create: `agent-discussion/frontend/src/components/common/RoleBadge.tsx`
- Create: `agent-discussion/frontend/src/components/common/ConnectionDot.tsx`
- Create: `agent-discussion/frontend/src/components/common/common.module.css`

- [ ] **Step 1: 创建 common.module.css**

```css
/* --- RoleBadge --- */
.roleBadge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
  letter-spacing: 0.02em;
}

.roleInitial {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--ink-inverse);
}

/* --- ConnectionDot --- */
.connectionDot {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--ink-muted);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.dotConnected { background: #5A9A6A; }
.dotDisconnected { background: #C49A6C; animation: pulse 1.5s infinite; }
.dotError { background: #C45A5A; }

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
```

- [ ] **Step 2: 创建 RoleBadge.tsx**

```tsx
import { getRoleStyle } from '../../constants';
import styles from './common.module.css';

interface RoleBadgeProps {
  name: string;
}

export function RoleBadge({ name }: RoleBadgeProps) {
  const style = getRoleStyle(name);
  return (
    <span className={styles.roleBadge} style={{ background: style.background, color: style.ink }}>
      <span className={styles.roleInitial} style={{ background: style.color }}>
        {style.initial}
      </span>
      {style.label}
    </span>
  );
}
```

- [ ] **Step 3: 创建 ConnectionDot.tsx**

```tsx
import styles from './common.module.css';

interface ConnectionDotProps {
  status: 'connected' | 'disconnected' | 'error';
}

const LABEL_MAP: Record<string, string> = {
  connected: '已连接',
  disconnected: '连接中…',
  error: '连接失败',
};

export function ConnectionDot({ status }: ConnectionDotProps) {
  const dotClass = status === 'connected'
    ? styles.dotConnected
    : status === 'error'
      ? styles.dotError
      : styles.dotDisconnected;

  return (
    <span className={styles.connectionDot}>
      <span className={`${styles.dot} ${dotClass}`} />
      {LABEL_MAP[status] ?? status}
    </span>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add agent-discussion/frontend/src/components/common/
git commit -m "feat(frontend): add RoleBadge and ConnectionDot components"
```

---

## Task 8: 进度感知组件

**Files:**
- Create: `agent-discussion/frontend/src/components/Progress/ProgressBar.tsx`
- Create: `agent-discussion/frontend/src/components/Progress/ProgressBar.module.css`
- Create: `agent-discussion/frontend/src/components/Progress/AgentStatusPanel.tsx`
- Create: `agent-discussion/frontend/src/components/Progress/AgentStatusPanel.module.css`

- [ ] **Step 1: 创建 ProgressBar.module.css**

```css
.progressBar {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 12px 32px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  position: relative;
}

.stepDot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border-medium);
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.stepDot.completed { background: var(--accent); }
.stepDot.active {
  background: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  animation: stepPulse 2s infinite;
}

.stepLabel {
  font-size: 12px;
  color: var(--ink-muted);
  font-weight: 400;
  transition: color 0.3s ease;
  white-space: nowrap;
}

.stepLabel.completed { color: var(--ink-secondary); }
.stepLabel.active {
  color: var(--accent);
  font-weight: 500;
}

.stepConnector {
  flex: 1;
  height: 1px;
  background: var(--border-light);
  margin: 0 4px;
}

.stepConnector.completed { background: var(--accent-soft); }

.roundCounter {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--accent);
  margin-left: 4px;
}

@keyframes stepPulse {
  0%, 100% { box-shadow: 0 0 0 3px var(--accent-soft); }
  50% { box-shadow: 0 0 0 5px var(--accent-soft); }
}
```

- [ ] **Step 2: 创建 ProgressBar.tsx**

```tsx
import type { DiscussionPhase, RoundProgress } from '../../types';
import { PHASE_ORDER, PHASE_LABELS } from '../../constants';
import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  currentPhase: DiscussionPhase;
  roundProgress: RoundProgress | null;
}

export function ProgressBar({ currentPhase, roundProgress }: ProgressBarProps) {
  const currentIndex = currentPhase === 'done'
    ? PHASE_ORDER.length
    : PHASE_ORDER.indexOf(currentPhase);

  return (
    <div className={styles.progressBar}>
      {PHASE_ORDER.map((phase, index) => {
        const isCompleted = index < currentIndex;
        const isActive = index === currentIndex && currentPhase !== 'done' && currentPhase !== 'idle';
        const dotClass = [
          styles.stepDot,
          isCompleted ? styles.completed : '',
          isActive ? styles.active : '',
        ].filter(Boolean).join(' ');
        const labelClass = [
          styles.stepLabel,
          isCompleted ? styles.completed : '',
          isActive ? styles.active : '',
        ].filter(Boolean).join(' ');

        return (
          <div className={styles.step} key={phase}>
            <span className={dotClass} />
            <span className={labelClass}>
              {PHASE_LABELS[phase]}
              {isActive && phase === 'discussion' && roundProgress && (
                <span className={styles.roundCounter}>
                  {roundProgress.current}/{roundProgress.total}
                </span>
              )}
            </span>
            {index < PHASE_ORDER.length - 1 && (
              <span className={`${styles.stepConnector} ${isCompleted ? styles.completed : ''}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: 创建 AgentStatusPanel.module.css**

```css
.panel {
  display: flex;
  gap: 2px;
  padding: 8px 32px;
  background: var(--bg-page);
  border-bottom: 1px solid var(--border-light);
  overflow-x: auto;
}

.agentCard {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: var(--radius-medium);
  background: var(--bg-card);
  min-width: 0;
  flex: 1;
  transition: all 0.2s ease;
}

.agentCard.thinking {
  border: 1px solid var(--accent-soft);
  background: #FFFBF8;
}

.avatar {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--ink-inverse);
  flex-shrink: 0;
}

.agentName {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.statusText {
  font-size: 11px;
  color: var(--ink-muted);
  margin-left: auto;
  white-space: nowrap;
}

.statusText.thinking {
  color: var(--accent);
}

.thinkingDots {
  display: inline-flex;
  gap: 2px;
  margin-left: 2px;
}

.thinkingDot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1.4s infinite;
}

.thinkingDot:nth-child(2) { animation-delay: 0.2s; }
.thinkingDot:nth-child(3) { animation-delay: 0.4s; }
```

- [ ] **Step 4: 创建 AgentStatusPanel.tsx**

```tsx
import type { AgentInfo, AgentState } from '../../types';
import { getRoleStyle } from '../../constants';
import styles from './AgentStatusPanel.module.css';

interface AgentStatusPanelProps {
  agents: AgentInfo[];
  agentStates: Record<string, AgentState>;
}

function AgentStatusLabel({ state }: { state: AgentState | undefined }) {
  if (!state || state.status === 'idle') {
    return <span className={styles.statusText}>等待</span>;
  }
  if (state.status === 'thinking') {
    return (
      <span className={`${styles.statusText} ${styles.thinking}`}>
        思考
        <span className={styles.thinkingDots}>
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
        </span>
      </span>
    );
  }
  return <span className={styles.statusText}>已发言({state.speakCount})</span>;
}

export function AgentStatusPanel({ agents, agentStates }: AgentStatusPanelProps) {
  if (agents.length === 0) return null;

  return (
    <div className={styles.panel}>
      {agents.map(agent => {
        const role = getRoleStyle(agent.name);
        const state = agentStates[agent.name];
        const isThinking = state?.status === 'thinking';

        return (
          <div
            key={agent.name}
            className={`${styles.agentCard} ${isThinking ? styles.thinking : ''}`}
          >
            <span className={styles.avatar} style={{ background: role.color }}>
              {role.initial}
            </span>
            <span className={styles.agentName}>{role.label}</span>
            <AgentStatusLabel state={state} />
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add agent-discussion/frontend/src/components/Progress/
git commit -m "feat(frontend): add ProgressBar and AgentStatusPanel components"
```

---

## Task 9: Timeline 组件（消息气泡、阶段分隔线、投票卡片、打字指示器）

**Files:**
- Create: `agent-discussion/frontend/src/components/Timeline/MessageBubble.tsx`
- Create: `agent-discussion/frontend/src/components/Timeline/MessageBubble.module.css`
- Create: `agent-discussion/frontend/src/components/Timeline/PhaseDivider.tsx`
- Create: `agent-discussion/frontend/src/components/Timeline/VotingCard.tsx`
- Create: `agent-discussion/frontend/src/components/Timeline/VotingCard.module.css`
- Create: `agent-discussion/frontend/src/components/Timeline/TypingIndicator.tsx`

- [ ] **Step 1: 创建 MessageBubble.module.css**

签名细节（120% 精致点）：消息气泡左侧不用圆角 border accent 条（反 AI slop），改用头像字母 + 极细的 accent 线做身份识别。头像是纯色字母方块，衬线斜体引语感。

```css
.bubble {
  display: flex;
  gap: 14px;
  padding: 18px 0;
  animation: fadeInUp 0.3s ease-out both;
}

.bubble + .bubble {
  border-top: 1px solid var(--border-light);
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--ink-inverse);
  flex-shrink: 0;
  margin-top: 2px;
}

.contentWrapper {
  flex: 1;
  min-width: 0;
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.authorName {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 14px;
}

.timestamp {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-muted);
  margin-left: auto;
}

.content {
  font-size: 14px;
  line-height: 1.75;
  color: var(--ink-primary);
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 2: 创建 MessageBubble.tsx**

```tsx
import { useMemo } from 'react';
import type { Message } from '../../types';
import { getRoleStyle } from '../../constants';
import { RoleBadge } from '../common/RoleBadge';
import { renderMarkdown } from '../../utils/markdown';
import { formatTime } from '../../utils/time';
import styles from './MessageBubble.module.css';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const role = getRoleStyle(message.name);
  const htmlContent = useMemo(() => renderMarkdown(message.content), [message.content]);

  return (
    <div className={styles.bubble}>
      <div className={styles.avatar} style={{ background: role.color }}>
        {role.initial}
      </div>
      <div className={styles.contentWrapper}>
        <div className={styles.header}>
          <span className={styles.authorName} style={{ color: role.ink }}>
            {message.name}
          </span>
          <RoleBadge name={message.name} />
          <span className={styles.timestamp}>{formatTime(message.timestamp)}</span>
          </div>
          <div className={styles.body} dangerouslySetInnerHTML={{ __html: htmlContent }} />
        </div>
      </div>
    );
}
```

- [ ] **Step 3:** 创建 PhaseDivider（阶段分割线）、VotingCard（投票结果卡片）、TypingIndicator（打字指示器）组件
- [ ] **Step 4: Commit**

---

### Task 10: Timeline 主容器

**Files:**
- Create: `frontend/src/components/Timeline/Timeline.tsx`
- Create: `frontend/src/components/Timeline/Timeline.module.css`

- [ ] **Step 1:** 创建 Timeline 容器，渲染消息列表 + PhaseDivider + VotingCard，自动滚动到底部
- [ ] **Step 2: Commit**

---

### Task 11: Sidebar 组件

**Files:**
- Create: `frontend/src/components/Sidebar/Sidebar.tsx` + `.module.css`
- Create: `frontend/src/components/Sidebar/SessionList.tsx`
- Create: `frontend/src/components/Sidebar/ReportList.tsx`

- [ ] **Step 1:** SessionList — 从 localStorage 读取历史会话列表，点击切换
- [ ] **Step 2:** ReportList — 调用 `GET /api/reports` 获取报告列表，点击预览
- [ ] **Step 3:** Sidebar 容器 — Tab 切换（会话 / 报告）
- [ ] **Step 4: Commit**

---

### Task 12: TopBar + InputBar

**Files:**
- Create: `frontend/src/components/TopBar/TopBar.tsx` + `.module.css`
- Create: `frontend/src/components/InputBar/InputBar.tsx` + `.module.css`

- [ ] **Step 1:** TopBar — 话题标题 + 状态指示 + 导出/设置按钮
- [ ] **Step 2:** InputBar — 底部输入栏，话题输入 + 发送 + 追问输入
- [ ] **Step 3: Commit**

---

### Task 13: Settings 配置面板

**Files:**
- Create: `frontend/src/components/Settings/SettingsPanel.tsx` + `.module.css`

- [ ] **Step 1:** 讨论轮数滑块（1-10）+ 模型选择下拉框，通过 WebSocket `start` action 携带参数
- [ ] **Step 2: Commit**

---

### Task 14: Report 报告预览 + Welcome 欢迎页

**Files:**
- Create: `frontend/src/components/Report/ReportViewer.tsx` + `.module.css`
- Create: `frontend/src/components/Welcome/Welcome.tsx` + `.module.css`

- [ ] **Step 1:** ReportViewer — fetch 报告 + marked.js 渲染 + 全屏预览
- [ ] **Step 2:** Welcome — 空白欢迎页，引导输入话题
- [ ] **Step 3: Commit**

---

### Task 15: Export 导出功能

**Files:**
- Create: `frontend/src/utils/export.ts`

- [ ] **Step 1:** 实现 `exportMarkdown()`（下载 .md）、`exportPDF()`（window.print）、`exportScreenshot()`（html2canvas）
- [ ] **Step 2: Commit**

---

### Task 16: App.tsx 主布局

**Files:**
- Create: `frontend/src/App.tsx` + `App.module.css`
- Create: `frontend/src/main.tsx`

- [ ] **Step 1:** 组装：Sidebar（左）+ Main（TopBar + ProgressBar + AgentStatusPanel + Timeline + InputBar）
- [ ] **Step 2:** 用 useWebSocket / useSession 管理全局状态，props 向下传递
- [ ] **Step 3: Commit**

---

### Task 17: 后端新增 WebSocket 事件

**Files:**
- Modify: `src/web_server.py`

- [ ] **Step 1:** 新增 `round_progress` 事件 — 推送当前轮次/总轮次
- [ ] **Step 2:** 新增 `agent_status` 事件 — 推送 Agent 状态（thinking/speaking/waiting）
- [ ] **Step 3:** 新增 `pipeline_log` 事件 — 推送阶段耗时和 token 用量
- [ ] **Step 4: Commit**

---

### Task 18: 后端新增 REST API

**Files:**
- Modify: `src/web_server.py`

- [ ] **Step 1:** `POST /api/sessions` — 保存会话到 `sessions/` 目录 JSON 文件
- [ ] **Step 2:** `GET /api/sessions` + `GET /api/sessions/{id}` — 列出/读取历史会话
- [ ] **Step 3: Commit**

---

### Task 19: Vite 生产构建集成

**Files:**
- Modify: `src/web_server.py`

- [ ] **Step 1:** 修改后端 serve 逻辑 — 优先 serve `frontend/dist/` 目录
- [ ] **Step 2:** 添加 `npm run build` 到构建流程
- [ ] **Step 3: Commit**

---

### Task 20: 集成测试

- [ ] **Step 1:** 启动后端 `python run_web.py`
- [ ] **Step 2:** 启动前端 `cd frontend && npm run dev`
- [ ] **Step 3:** 验证 WebSocket 连接、讨论流程、导出、会话持久化
- [ ] **Step 4:** 构建生产版本 `npm run build`，验证后端 serve 静态文件
