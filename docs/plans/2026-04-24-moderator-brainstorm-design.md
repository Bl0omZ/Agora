# 主持人 Brainstorm 议题精炼 + Agent 模型展示 设计文档

**日期**：2026-04-24
**作者**：lvzhibo + AI（brainstorming → ralplan 共识规划）
**状态**：✅ APPROVED（Critic Round 2 通过）｜ 实施中（详见文末「实施进度」章节）

---

## 0. 背景与目标

为 `agora` 增加两个能力：

1. **UI 增强**：Agent 状态卡片显示所属模型；主持人作为特殊角色卡片混入面板
2. **流程增强**：在原讨论开始前新增「主持人 brainstorm 议题精炼」阶段，主持人通过多轮 Q&A 与用户对齐需求

---

## 1. 核心架构决策

### 1.1 关于"使用 skill"的关键说明

**结论：当前架构无法原生使用 skill，采用 Prompt-as-Skill 等价方案**。

| 维度 | 说明 |
|---|---|
| skill 是什么 | Claude Code / Copilot CLI 等 agent runtime 的概念，依赖 markdown 加载 + 工具调用循环 |
| 当前架构 | Semantic Kernel 的 `GroupChatOrchestration`，每个 agent 是单次 LLM 调用，无 agent runtime |
| 等价方案 | 把 brainstorming skill 的方法论提炼为 prompt template，注入到主持人 LLM 调用 |

### 1.2 决策表

| 决策点 | 结论 | 理由 |
|---|---|---|
| skill 是否原生可用 | 否，用 Prompt-as-Skill | SK 架构限制 |
| 主持人精炼形态 | 多轮 Q&A 对话 | 用户明确要求"先与用户确认需求" |
| brainstorm 提问策略 | 多选+自由输入混合 (5=C+A) | brainstorming skill 原则 |
| 轮数控制 | 主持人自主 + max 上限 + 用户跳过 (4=C+D) | 灵活+安全+用户主导 |
| 精炼后议题传递 | 只传精炼议题给 agents (6=A) | agents 上下文干净 |
| 主持人 UI 位置 | 特殊卡片混入 Agent 面板 (7=C) | 主角化心智模型 |
| Brainstorm 消息呈现 | 作为 timeline message 子类型 | Architect Round 1 反命题部分采纳 |

### 1.3 五条核心原则

1. **不破坏现有架构** — 新增阶段优雅插入，不重写 GroupChatOrchestration
2. **后端先于前端就绪** — WebSocket 协议是契约
3. **用户始终可逃逸** — 任何时候都能"跳过"或"直接开始"
4. **YAGNI 严格执行** — 不做模板库、不做主持人之间多轮反思、不做局部编辑
5. **失败安全（fail-safe）** — JSON 格式异常、用户长时间无响应、连接断开都要有兜底

---

## 2. 新会话生命周期

```
idle → brainstorming（新增） → discussion → voting → summary → saved
                ↑
       ├─ 主持人提问（含 multi-choice options）
       ├─ 用户回答（点选 or 自由输入）
       ├─ ...循环（主持人自主判断 or 上限触发 or 用户点"跳过"）
       └─ 主持人产出"精炼议题" → 用户最终确认 → 进入 discussion
```

---

## 3. 数据模型

### 3.1 后端 `models.py` 新增

```python
class BrainstormConfig(BaseModel):
    """主持人议题精炼阶段配置"""
    enabled: bool = True
    max_rounds: int = 5  # 主持人最多问几轮（兜底）
    answer_timeout_seconds: int = 300  # 用户无响应超时
    system_prompt: str = (
        "You are a discussion moderator. Before the panel discussion starts, "
        "your job is to refine the user's topic into a precise, well-scoped question.\n"
        "Ask ONE clarifying question at a time. Output JSON: "
        '{"action": "ask" | "finalize", '
        '"question": "...", '
        '"options": ["choice1", "choice2", "choice3"], '
        '"allow_freetext": true, '
        '"refined_topic": "..." (only when action=finalize), '
        '"context_summary": "..." (only when action=finalize)}'
    )

class AppConfig(BaseModel):
    agents: list[AgentConfig]
    discussion: DiscussionConfig = DiscussionConfig()
    voting: VotingConfig = VotingConfig()
    brainstorm: BrainstormConfig = BrainstormConfig()  # 新增
    manager_service_index: int = 0
    supports_structured_output: bool = True
```

### 3.2 SessionMeta schema_version

```json
{
  "schema_version": 2,
  "topic": "...",
  "refined_topic": "...",      // 仅 v2+
  "brainstorm_history": [...]  // 仅 v2+
}
```

旧会话（无 `schema_version` 或 `=1`）回放时视为已跳过 brainstorm。

---

## 4. WebSocket 协议

| 方向 | type | payload | 时机 |
|---|---|---|---|
| ← 服务器 | `agent_meta` | `{agents: [{name, model, role, is_moderator}]}` | 会话开始时一次性推送 |
| ← 服务器 | `phase_changed` | `{phase: 'brainstorming' \| 'discussion' \| ...}` | 进入新阶段 |
| ← 服务器 | `moderator_question` | `{round, question, options[], allow_freetext, model}` | 主持人发问 |
| → 客户端 | `moderator_answer` | `{round, answer}` | 用户回答 |
| → 客户端 | `brainstorm_skip` | `{}` | 用户点"直接开始讨论" |
| ← 服务器 | `topic_refined` | `{original, refined, context_summary?}` | 主持人产出最终精炼 |
| → 客户端 | `topic_confirmed` | `{accept: true}` | 用户点"开始讨论" |
| ← 服务器 | `brainstorm_timeout` | `{}` | 5 分钟无响应 |

---

## 5. 文件结构变更

### 后端

```
agora/src/
├── models.py        ← 新增 BrainstormConfig
├── brainstorm.py    ← 新文件：BrainstormSession 引擎
├── discussion.py    ← 修改：在 run_discussion 前调用 brainstorm
└── web_server.py    ← 修改：新增 5 个 WS 事件 + agent_meta 推送 + pending_answers
```

### 前端

```
agora/frontend/src/
├── types.ts                                 ← 新增类型 + AgentInfo 加 model/is_moderator
├── hooks/useWebSocket.ts                    ← 新增事件处理
├── components/
│   ├── Brainstorm/
│   │   ├── ModeratorQuestion.tsx           ← 新建：主持人发问卡
│   │   ├── ModeratorQuestion.module.css
│   │   ├── TopicConfirm.tsx                ← 新建：精炼议题确认卡
│   │   └── TopicConfirm.module.css
│   ├── Progress/AgentStatusPanel.tsx       ← 改造：双行+主持人特殊卡
│   └── Progress/AgentStatusPanel.module.css
└── App.tsx                                  ← 路由 brainstorming 阶段
```

---

## 6. 核心代码骨架

### 6.1 `brainstorm.py`

```python
class BrainstormSession:
    """主持人议题精炼会话，管理多轮 Q&A 状态"""

    def __init__(self, config: BrainstormConfig, kernel, service_id: str,
                 on_question: Callable[[dict], Awaitable[str]]):
        self.config = config
        self.kernel = kernel
        self.service_id = service_id
        self.on_question = on_question  # 回调：发问后等待用户回答
        self.history: list[dict] = []

    async def run(self, original_topic: str) -> dict:
        """
        Returns: {refined_topic, context_summary, history}
        - action=ask  → 调 on_question 等用户回答 → 继续
        - action=finalize → 返回精炼结果
        - 触达 max_rounds → 强制让 LLM finalize
        - on_question 抛 SkipBrainstormException → 当前 history 强制 finalize
        """
```

### 6.2 `web_server.py` WS 挂起机制

```python
pending_answers: dict[str, asyncio.Future] = {}

async def _wait_user_answer(session_id, question_payload):
    fut = asyncio.get_event_loop().create_future()
    pending_answers[session_id] = fut
    await ws.send_json({"type": "moderator_question", **question_payload})
    try:
        return await asyncio.wait_for(fut, timeout=config.brainstorm.answer_timeout_seconds)
    except asyncio.TimeoutError:
        await ws.send_json({"type": "brainstorm_timeout"})
        raise SkipBrainstormException()
```

### 6.3 `AgentStatusPanel.tsx` 双行卡片

```tsx
<div className={styles.agentCard}>
  <span className={styles.avatar}>...</span>
  <div className={styles.textCol}>
    <div className={styles.row1}>
      <span className={styles.agentName}>{role.label}</span>
      {agent.is_moderator && <span className={styles.badge}>主持人</span>}
    </div>
    <div className={styles.row2}>
      <span className={styles.modelTag}>{agent.model}</span>
      <AgentStatusLabel state={state} />
    </div>
  </div>
</div>
```

主持人卡片用 `--accent-amber`（区别于普通 agent 的 blue）。

---

## 7. UI 视觉指导（huashu-design）

按 huashu-design 反 AI slop 原则：

- **主持人发问卡片**：窄色带边框 + 单色图标，不用圆角 accent border
- **多选选项**：横向 chip 按钮，hover 时 `box-shadow Y+2px` 微妙下沉
- **精炼议题确认卡**：仪式感强 — 双栏对比"原议题/精炼议题" + 居中"开始讨论"主按钮
- **跳过按钮**：低权重位置（右上角 link 风格"跳过澄清 →"）
- **timeline 消息流统一**：`moderator_question` / `user_answer` / `topic_refined` 作为 message 子类型，timeline 根据 `message.type` 路由到对应渲染器

---

## 8. 验收标准（Acceptance Criteria）

### 特性 1：Agent 模型展示

- [ ] AC1.1：每个 agent 卡片可见其 `model` 字段（如 `gpt-4o`）
- [ ] AC1.2：主持人卡片可见 `主持人` badge 且使用区别于普通 agent 的颜色
- [ ] AC1.3：当 model 字符串长度超过 20 时，CSS 自动 truncate 加 tooltip 显示完整名

### 特性 2：主持人 brainstorm 议题精炼

- [ ] AC2.1：用户输入议题后 3 秒内收到第一条 `moderator_question` 事件
- [ ] AC2.2：每个 `moderator_question` 必须包含 `options[]`（≥2 个）和 `allow_freetext: bool`
- [ ] AC2.3：brainstorm 对话最多 5 轮（含主持人发问），第 5 轮后强制 finalize
- [ ] AC2.4：用户点"跳过"按钮后，2 秒内进入 discussion 阶段
- [ ] AC2.5：精炼议题字符数 ≤ 300，超过则截断+省略号
- [ ] AC2.6：精炼议题中不得包含 brainstorm 对话原文（agents 上下文必须干净）
- [ ] AC2.7：历史会话（无 `schema_version` 字段）回放时正常显示 discussion，不报错

### 特性 3：失败安全

- [ ] AC3.1：用户 5 分钟无响应 → 推送 `brainstorm_timeout`，前端弹 modal 三选项
- [ ] AC3.2：主持人 LLM 输出非 JSON → 重试 1 次，仍失败则强制 finalize 用原议题
- [ ] AC3.3：WS 断连重连后 brainstorm 状态可恢复（localStorage 缓存 history）

---

## 9. 实施分阶段

### 阶段 1：UI 增强（独立可发布）
- 后端：`AppConfig` 加载时推送 `agent_meta` 事件
- 前端：`AgentStatusPanel` 改造为双行卡片 + 主持人特殊样式
- **可独立上线**

### 阶段 2：BrainstormConfig + 后端骨架
- `models.py` 新增 `BrainstormConfig`
- 新建 `brainstorm.py`：`BrainstormSession` 类
- `web_server.py` 新增 `pending_answers` 和 WS 事件处理
- 阶段切换：`brainstorming → discussion`

### 阶段 3：前端 Brainstorm UI
- 新建 `Brainstorm/ModeratorQuestion.tsx` + `TopicConfirm.tsx`
- 接入 huashu-design 视觉语言
- `App.tsx` 路由 `phase === 'brainstorming'`

### 阶段 4：联调 + 收尾
- `brainstorm_skip` 事件全链路
- 精炼议题不满意 → 重新 brainstorm

---

## 10. ADR（Architecture Decision Record）

**Decision**：采用 Prompt-as-Skill 模式，新增 brainstorming 阶段，主持人通过多轮 Q&A 精炼议题，并作为 timeline message 子类型展现。

**Drivers**：
1. 现有 SK GroupChatOrchestration 不支持 agent 加载 skill
2. 用户明确要求"先与用户确认精准需求"
3. 工程代价必须可控（单 PR 范围）

**Alternatives Considered**：
- B（Agent Runtime 改造）— 否决：10x 工程量
- C（单次精炼）— 否决：不满足"双向对话"需求
- 把 brainstorm 做成 discussion 第 0 轮（Architect 反命题）— 部分采纳：保留新阶段但消息流统一

**Why Chosen**：A 在满足需求和工程代价之间最平衡，且通过采纳 Architect 的"消息流统一"建议，将状态机复杂度降到最低。

**Consequences**：
- ✅ 用户获得结构化的议题精炼体验
- ✅ Agents 上下文保持干净
- ⚠️ 需要新增 5 个 WS 事件 + 1 个后端阶段 + 2 个前端组件
- ⚠️ session_meta 需要加 `schema_version` 字段以兼容历史会话

**Follow-ups**：
- 上线后观察 brainstorm 平均轮数，若 >3 考虑优化 system_prompt
- 收集用户"跳过"率，若 >50% 说明价值被质疑，需要重新设计
- 未来可考虑加 brainstorm 模板库（now: YAGNI 否决）

---

## 11. 风险评估

| 风险 | 严重度 | 缓解 |
|---|---|---|
| LLM JSON 格式错误 | 中 | `supports_structured_output` + 解析失败强制 finalize（AC3.2） |
| WS 挂起永不返回 | 高 | `pending_answers` 5 分钟 timeout + Modal 兜底（AC3.1） |
| 历史会话回放崩溃 | 中 | session_meta 加 `schema_version`，旧会话视为已跳过（AC2.7） |
| brainstorm 阶段刷新丢状态 | 中 | localStorage 持久化 history，重连恢复（AC3.3） |

---

## 12. 实施进度（截至 2026-04-24）

> 真实进度盘点。每项标注：✅ 完成 / 🚧 部分完成 / 📋 未开始 / ❌ 已撤销。
> 见 `KNOWN_ISSUES.md` 中关联的具体问题。

### 阶段 1：UI 增强（独立可发布）

| 项目 | 状态 | 备注 |
|---|---|---|
| 后端推送 `agent_meta` 事件 | 📋 未开始 | `web_server.py::_run_session_pipeline` 中尚未添加；前端拿不到 model 数据 |
| 前端 `AgentStatusPanel` 双行卡片改造 | 🚧 部分完成 | 组件结构已支持双行展示，但缺主持人 badge 与模型 tag 渲染（依赖 `agent_meta`） |
| 主持人卡片特殊颜色 | 📋 未开始 | CSS 待加 `--accent-amber` 变体 |

**结论**：阶段 1 **不能独立上线**，被 `agent_meta` 推送阻塞。详见 `KNOWN_ISSUES.md` #5。

### 阶段 2：BrainstormConfig + 后端骨架

| 项目 | 状态 | 备注 |
|---|---|---|
| `models.py::BrainstormConfig` | ✅ 完成 | 包含 `enabled` / `max_rounds` / `answer_timeout_seconds` / `system_prompt` |
| `models.py::AppConfig.brainstorm` | ✅ 完成 | 已加入 |
| `src/brainstorm.py` 新建 | ✅ 完成 | `BrainstormSession` 17KB 已存在，含降级策略 |
| `web_server.py::pending_brainstorm_answers` | ✅ 完成 | dict 已声明 |
| `web_server.py::wait_user_brainstorm_answer` | ✅ 完成 | 函数已实现，含 timeout 兜底 |
| WS 事件 `moderator_question` / `moderator_answer` / `topic_refined` / `topic_confirmed` / `brainstorm_timeout` | 🚧 部分完成 | 服务端发送路径已铺，但**未与真实流程串联**（discussion.py 入口未调用 brainstorm） |
| 阶段切换 `brainstorming → discussion` | 📋 未开始 | `_run_session_pipeline` 仍直接进 discussion |

**结论**：阶段 2 **后端骨架就绪，但未串联进主流程**。

### 阶段 3：前端 Brainstorm UI

| 项目 | 状态 | 备注 |
|---|---|---|
| `frontend/src/components/Brainstorm/ModeratorQuestion.tsx` | 📋 未开始 | 目录不存在 |
| `frontend/src/components/Brainstorm/TopicConfirm.tsx` | 📋 未开始 | 同上 |
| `App.tsx` 路由 `phase === 'brainstorming'` | 📋 未开始 | 当前 App.tsx 无该分支 |
| `useWebSocket.ts` 处理新事件 | 📋 未开始 | |

**结论**：阶段 3 **完全未开始**。详见 `KNOWN_ISSUES.md` #4。

### 阶段 4：联调 + 收尾

| 项目 | 状态 | 备注 |
|---|---|---|
| `brainstorm_skip` 全链路 | 📋 未开始 | |
| 精炼议题不满意 → 重新 brainstorm | 📋 未开始 | |
| localStorage 持久化 brainstorm history（AC3.3） | 📋 未开始 | |
| schema_version 写入 sessions/*.json（AC2.7） | 📋 未开始 | 当前回放仍按 v1 处理，无报错风险 |

**结论**：阶段 4 **未开始**。

### 验收标准（AC）总览

| AC ID | 描述 | 状态 |
|---|---|---|
| AC1.1 | agent 卡片可见 model | 📋 |
| AC1.2 | 主持人 badge + 区别色 | 📋 |
| AC1.3 | model 长度 truncate + tooltip | 📋 |
| AC2.1 | 议题输入后 3s 内首条 `moderator_question` | 📋 |
| AC2.2 | 每问含 `options[]` ≥2 + `allow_freetext` | 🚧 后端能产，但前端没接 |
| AC2.3 | 最多 5 轮强制 finalize | ✅ `BrainstormSession` 已实现 |
| AC2.4 | 跳过后 2s 内进入 discussion | 📋 |
| AC2.5 | 精炼议题 ≤300 字 | 🚧 后端 prompt 有要求但无强制截断 |
| AC2.6 | 精炼议题不含原文 | ✅ prompt 设计已隔离 |
| AC2.7 | 历史会话兼容回放 | ✅ 当前无 schema_version 字段时默认跳过 brainstorm |
| AC3.1 | 5 分钟超时 + Modal | 🚧 后端 timeout 已实现，前端 Modal 缺 |
| AC3.2 | LLM 非 JSON 重试 1 次 | ✅ `BrainstormSession` 含降级 |
| AC3.3 | WS 重连恢复 brainstorm 状态 | 📋 未实现 |

**总进度**：3 / 13 AC 完成，5 / 13 部分完成，5 / 13 未开始。

### 与本设计文档无关但本次会话发现的额外问题

详见 `KNOWN_ISSUES.md`：

- #1 `min_rounds` 守卫未真正生效（讨论流程被绕过）
- #2 user 消息 name 仍显示 "Unknown"
- #3 LLM `<think>` 标签污染投票 reason
- #6 FastAPI 未启 `--reload`（强烈怀疑 #1 #2 修复"未生效"的根因）

### 下一步推荐顺序

1. **修 #6**（启 `--reload`）—— 5 分钟工作量，可能直接让 #1 #2 自动生效
2. **回归验证 #1 #2** —— 看是否真的是热加载问题
3. **修 #3**（投票 reason 清洗）—— prompt 加约束 + 正则兜底
4. **完成阶段 1 的 `agent_meta` 推送**（KNOWN_ISSUES #5）—— 解锁前端模型展示
5. **完成阶段 3 前端 Brainstorm UI** —— 让阶段 2 的后端真正可用
6. **完成阶段 4 收尾事项**

