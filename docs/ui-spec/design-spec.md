# Agent Discussion — Visible Moderator Dispatch · UI Spec (React 草案版)

> 设计契约 · 与现有 React 架构对齐 · 2026-04-24
>
> **路线说明**：本 spec 最初按 huashu-design「独立 HTML 高保真原型」路线起草，
> 但因为 `agent-discussion/frontend` 已经是一个完整的 React 19 + TS + CSS Modules 工程，
> 中间产物 HTML mockup 无法直接照着实现，反而增加沟通成本。
> 现在路线已切到「React 组件草案 + 共享 token + dev 预览页」，所有产物都在
> `frontend/src/components/Brainstorm/` 与 `frontend/src/components/Timeline/HostMessage*` 下。
>
> **配套实施产物**（已落地）：
> - `frontend/src/types.ts` — 新增 `BrainstormQuestion` / `ComplexityAnalysis` / `DispatchPlan` / `HostMessageMeta` / `TopicRefinedPayload` / `BrainstormFailureState`
> - `frontend/src/styles/variables.css` — 新增 `--moderator-*`（amber 5 色）+ `--complexity-*`（low/medium/high 6 色）
> - `frontend/src/components/Brainstorm/BrainstormPanel.{tsx,module.css}` — 主持人提问 + 多选 chip + 自由输入 + 跳过 link
> - `frontend/src/components/Brainstorm/TopicConfirmCard.{tsx,module.css}` — 进入 discussion 前的精炼议题确认大卡
> - `frontend/src/components/Brainstorm/BrainstormStates.{tsx,module.css}` — `BrainstormNotice` + `BrainstormSkipConfirm` + `BrainstormLoadingPlaceholder`
> - `frontend/src/components/Timeline/HostMessage.{tsx,module.css}` — Host 三 variant：normal / complexity / dispatch
> - `frontend/src/components/Brainstorm/PreviewGallery.{tsx,module.css}` — dev 预览页，访问 `/?preview=brainstorm`
> - `frontend/src/components/Progress/AgentStatusPanel.module.css` — 把硬编码的 amber 改为 `var(--moderator)`
>
> **dev 预览**：
> ```
> cd agent-discussion/frontend
> npm run dev
> # 浏览器打开 http://localhost:5173/?preview=brainstorm
> ```

---

## 0. 设计哲学锚点（反 AI slop self-check）

本设计遵循三条与现有 `agent-discussion` 前端一致的视觉语法：

| 锚点 | 体现 | 反对什么 |
|---|---|---|
| **诚实的 border** | 1px solid `var(--border-light)` 划界，刻意不用 box-shadow 显眼度 | ❌ 浮夸 box-shadow / 紫渐变 |
| **克制的色** | 全部色值来自 `variables.css` 或 VotingCard 的 approve/oppose/neutral 三色 | ❌ 凭空发明色 / 圆角左侧 accent border |
| **结构化文字** | 文案用「」引号 + `text-wrap: pretty` | ❌ emoji 当 icon / 三段式 SEO 废话 |

**color token 增量**（已写入 `variables.css`）：

```css
/* Moderator (amber) —— Brainstorming 阶段主持人调度专属 */
--moderator:        #B7791F;
--moderator-bg:     #FEF3C7;
--moderator-soft:   #FFFBEB;
--moderator-border: #FCD34D;
--moderator-ink:    #78350F;

/* Complexity levels —— 沿用 VotingCard 三色立场体系，不另起新词汇 */
--complexity-low:        #2E7D32;  --complexity-low-bg:    #E8F5E9;
--complexity-medium:     #F57F17;  --complexity-medium-bg: #FFF8E1;
--complexity-high:       #C62828;  --complexity-high-bg:   #FFEBEE;
```

理由：amber 与 VotingCard neutral `#F57F17` 同色相不同明度，作为「调度角色」既不与立场三色冲突、又能形成视觉锚点。复杂度三色直接复用 VotingCard 立场色，让用户的视觉记忆复用——不造新词汇。

---

## 1. 组件清单 · 已落地 React 组件

### 场景 A · Brainstorming 底部交互卡

| 组件 | 文件 | 职责 |
|---|---|---|
| `<BrainstormPanel>` | `Brainstorm/BrainstormPanel.tsx` | 主持人发问（amber 头像 + badge）+ 多选/单选 chip + 自由输入 textarea + 跳过 link + 提交按钮 |

接入位置：`App.tsx` 中当 `phase === 'brainstorming' && pendingQuestion` 时，把 `<InputBar>` 替换为 `<BrainstormPanel>`。

Props 契约：
```ts
{
  question: BrainstormQuestion;
  submitting?: boolean;
  onSubmit: (answer: BrainstormAnswer) => void;
  onSkip: () => void;  // 由上层弹 BrainstormSkipConfirm modal
}
```

### 场景 B · Timeline 内 Host 三种消息

| variant | 组件 | meta 字段 | 视觉 |
|---|---|---|---|
| normal | `<HostMessage>` (variant=normal) | `meta.variant === 'normal'` 或缺省 | amber 头像 + 主持人 badge + markdown 渲染的普通文字气泡 |
| complexity | `<HostMessage>` (variant=complexity) | `meta.complexity` | amber 头像 + 「复杂度判断」tag + 嵌入 ComplexitySubCard（chip + rationale + 维度 tag） |
| dispatch | `<HostMessage>` (variant=dispatch) | `meta.dispatch` | amber 头像 + 「派发计划」tag + 嵌入 DispatchSubCard（精炼议题 + agent 任务列表 + rationale） |

接入位置：`Timeline.tsx` 中 `messages.map` 时，若 `message.name === 'Host'` 用 `<HostMessage>`，否则维持现有 `<MessageBubble>`。

**回放兼容（PRD AC8）**：meta 缺失或 variant 未知时退化为 `normal` 渲染原始 content，旧 session JSON 可直接回放。

### 场景 C · AgentStatusPanel 增强（已对齐 token）

`AgentStatusPanel.tsx` 在之前的迭代里已支持：
- `agent.is_moderator === true` → 加上 `.moderator` 类
- `agent.model` → 渲染 model tag（hover 显示完整名）
- `state.status === 'thinking'` → 三点动画

本次只改 `AgentStatusPanel.module.css`：把硬编码的 `#f59e0b` / `#FFFBEB` / `#FFF4D6` 全部替换为 `var(--moderator-*)`，确保色源单一。

### 场景 D · TopicConfirm 大卡片（进入 discussion 前）

```
┌─────────────────────────────────────────────────┐ ← border-top: 3px solid var(--moderator)
│ 议题精炼完成   主持人已…           [重新精炼 ↺] │
├─────────────────────────────────────────────────┤
│ ╭─ 原议题 ───────────────────────────────────╮  │
│ │  「我们应该用 GraphQL 还是 REST？」           │  │
│ │  ↓ 精炼为                                   │  │
│ │  精炼议题                                   │  │
│ │  针对中型 SaaS 后端（5 个微服务、<50 人      │  │
│ │  团队），评估 GraphQL Federation vs REST    │  │
│ │  + BFF 在三个维度的权衡。                   │  │
│ ╰─────────────────────────────────────────────╯  │
│                                                 │
│ 复杂度  ● 中等                                  │
│         一句话理由 + 维度 tag                    │
│                                                 │
│ 派发计划  ╭─ A · Architect ──────────────╮      │
│           │  长期可扩展性 + Federation… │      │
│           │  期望产出：架构对比表       │      │
│           ╰─────────────────────────────╯      │
│           ╭─ P · Pragmatist ─────────────╮     │
│           │  团队学习曲线 + 落地成本…   │      │
│           ╰─────────────────────────────╯      │
│           ╭─ C · Challenger ─────────────╮     │
│           │  REST 反方论据 + 隐藏陷阱   │      │
│           ╰─────────────────────────────╯      │
│           "三角张力" rationale (italic)         │
├─────────────────────────────────────────────────┤
│                              [开始讨论 →]       │
└─────────────────────────────────────────────────┘
```

组件：`<TopicConfirmCard>`，文件 `Brainstorm/TopicConfirmCard.tsx`。

Props：
```ts
{
  payload: TopicRefinedPayload;
  submitting?: boolean;
  onConfirm: () => void;   // → 发送 topic_confirmed
  onRefine: () => void;    // → 回到 BrainstormPanel 重新走一轮
}
```

### 场景 E · 空/失败状态

`Brainstorm/BrainstormStates.tsx` 导出 3 个组件，按需组合：

| 组件 | 触发场景 | 视觉 |
|---|---|---|
| `<BrainstormNotice state={{kind: 'parse_failed'}}>` | LLM 重试 1 次仍非 JSON | 黄色 warn 信息条 + 圆形 `!` icon + 「主持人解析失败，已用原议题进入讨论」 |
| `<BrainstormNotice state={{kind: 'skipped'}}>` | 用户跳过澄清 | 蓝色 info 信息条 + 圆形 `i` icon |
| `<BrainstormNotice state={{kind: 'timeout'}}>` | `brainstorm_timeout` WS 事件 | 黄色 warn |
| `<BrainstormNotice state={{kind: 'reconnected'}}>` | 进页面时 localStorage 检测到未完成 | 绿色 success + `✓` |
| `<BrainstormSkipConfirm open onCancel onConfirm>` | 用户点 BrainstormPanel 的「跳过澄清」link | 阻断式 modal，红色「跳过，直接讨论」次按钮 |
| `<BrainstormLoadingPlaceholder>` | 用户提交 answer，等待下一个 question | 虚线边框 + 文字 + 三点动画 |

---

## 2. WebSocket 事件契约

> 设计原则：**可见叙事走 `message`，不可见控制走特殊事件**。
> 前端 Timeline 渲染只看 `message` 流，特殊事件只是触发 UI 表单态/弹窗状态。
> 这样历史会话回放只需要 replay `messages[]`、刷新重连不会因为漏控制事件丢叙事、
> Timeline 组件不需要为新阶段加新分支（只看 `message.meta.variant` 路由）。

### 服务端 → 客户端

| 事件 type | 进 Timeline | 用途 | payload |
|---|---|---|---|
| `phase` | ✅ 阶段分隔 | 阶段切换 | `{phase: 'brainstorming', label: '议题精炼'}` |
| `agent_meta` | ❌ → AgentStatusPanel | 一次性 | `{agents: AgentInfo[]}` |
| `message` Host normal | ✅ → HostMessage | 普通发言/承上启下 | `{name:'Host', meta:{variant:'normal'}}` |
| `message` Host complexity | ✅ 结构化卡 | 复杂度判断 | `{name:'Host', meta:{variant:'complexity', complexity: ComplexityAnalysis}}` |
| `message` Host dispatch | ✅ 结构化卡 | 派发计划 | `{name:'Host', meta:{variant:'dispatch', dispatch: DispatchPlan, refined_topic?}}` |
| `moderator_question` | ❌ → BrainstormPanel 表单态 | 控制 | `BrainstormQuestion` |
| `topic_refined` | ❌ → TopicConfirmCard 弹出 | 控制 | `TopicRefinedPayload` |
| `brainstorm_timeout` | ❌ → BrainstormNotice(kind=timeout) | 控制 | `{}` |
| `agent_status` | ❌ → AgentStatusPanel | 状态 | `{name, status: 'thinking'\|'idle'\|'spoken'\|'skipped'}` |

### 客户端 → 服务端

| 事件 type | 触发组件 | payload |
|---|---|---|
| `moderator_answer` | `<BrainstormPanel onSubmit>` | `BrainstormAnswer` |
| `brainstorm_skip` | `<BrainstormSkipConfirm onConfirm>` | `{}` |
| `topic_confirmed` | `<TopicConfirmCard onConfirm>` | `{accept: true}` |
| `topic_refine_again` | `<TopicConfirmCard onRefine>` | `{}` |

### 与现有 useWebSocket 的接入点

需要在 `frontend/src/hooks/useWebSocket.ts` 增量补：

```ts
// state
const [pendingQuestion, setPendingQuestion] = useState<BrainstormQuestion | null>(null);
const [pendingTopicRefined, setPendingTopicRefined] = useState<TopicRefinedPayload | null>(null);
const [brainstormFailure, setBrainstormFailure] = useState<BrainstormFailureState | null>(null);

// dispatch
case 'moderator_question': setPendingQuestion(data); break;
case 'topic_refined':      setPendingTopicRefined(data); break;
case 'brainstorm_timeout': setBrainstormFailure({kind: 'timeout'}); break;

// send actions
const submitBrainstormAnswer = (answer) => ws.send(JSON.stringify({type: 'moderator_answer', ...answer}));
const skipBrainstorm           = () => ws.send(JSON.stringify({type: 'brainstorm_skip'}));
const confirmTopic             = () => ws.send(JSON.stringify({type: 'topic_confirmed'}));
const refineAgain              = () => ws.send(JSON.stringify({type: 'topic_refine_again'}));
```

接入位置：`App.tsx` 在 `<InputBar>` 上方插入：
```tsx
{pendingQuestion && <BrainstormPanel question={pendingQuestion} onSubmit={...} onSkip={...} />}
{pendingTopicRefined && <TopicConfirmCard payload={pendingTopicRefined} onConfirm={...} onRefine={...} />}
{brainstormFailure && <BrainstormNotice state={brainstormFailure} onDismiss={() => setBrainstormFailure(null)} />}
```

---

## 3. 关键决策点

| ID | 决策点 | 当前选择 | 理由 |
|---|---|---|---|
| D1 | 主持人配色 | amber `#B7791F`（已落地 token） | 与 VotingCard neutral 同色相不打架，"调度"语义最强 |
| D2 | 复杂度等级粒度 | 3 级 low/medium/high | 信息密度优先，3 级足够指导讨论时长 |
| D3 | 派发计划是否必须用户确认 | **必须**，弹 `<TopicConfirmCard>` | 用户始终可逃逸 (PRD)，"开始讨论"是仪式感锚点 |
| D4 | Brainstorm 时 Timeline 是否仍可见 | **可见** | 用户可以滚回去看主持人之前说了什么 |
| D5 | 跳过按钮位置 | `<BrainstormPanel>` 右上角 link 风格 | 低权重 = 不诱导跳过，但始终可达 |
| D6 | LLM 失败兜底 | `<BrainstormNotice kind="parse_failed">` 信息条 | 不打断主流程，PRD 失败安全原则 |
| D7 | meta 缺失时的兼容 | `<HostMessage>` 退化为 normal variant 渲染原始 content | 满足 PRD AC8（旧 session 回放） |

---

## 4. 后续待办（前端 / 后端协作）

### 前端

1. ✅ types/CSS token/组件草案/PreviewGallery 已落地
2. ⏳ `useWebSocket.ts` 增加 `pendingQuestion` / `pendingTopicRefined` / `brainstormFailure` state + dispatch case
3. ⏳ `App.tsx` 在主流程里挂载 BrainstormPanel + TopicConfirmCard + BrainstormStates
4. ⏳ `Timeline.tsx` 路由 Host 消息到 `<HostMessage>`，其他消息维持 `<MessageBubble>`
5. ⏳ `useSession.ts` 持久化时把 `message.meta` 一起存（确认 `Message` 类型已扩展 `meta?: HostMessageMeta`）

### 后端

1. ⏳ `discussion.py` 实现 `BrainstormSession`（PRD §6.1）：发 `moderator_question` → 等 `moderator_answer` → 收敛 → 发 `topic_refined`
2. ⏳ Host 消息追加 `meta` 字段：normal / complexity / dispatch
3. ⏳ `web_server.py` 处理 `moderator_answer` / `brainstorm_skip` / `topic_confirmed` / `topic_refine_again` 入站事件
4. ⏳ 5 分钟超时定时器，超时后发 `brainstorm_timeout` 并继续走 fallback

### dev 验证

```bash
cd agent-discussion/frontend && npm run dev
# 打开 http://localhost:5173/?preview=brainstorm
# 点 chip / 输入文字 / 切换状态 / 点跳过看 modal / 点失败 chip 看 notice 切换
```
