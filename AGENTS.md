# AGENTS.md — Agora 项目记忆

> 本文档专为 AI 助手（Claude / Copilot / Codex）在新会话中**快速恢复上下文**而写。
> 人类维护者请在做出**架构性变更**或**关键决策**后更新本文档。
> 最近一次更新：2026-05-05。

---

## 0. 2026-05-05 功能增量

本轮把固定三人讨论升级为 preset 驱动的 agent 池，并在总结后生成可导出的 Agent System Blueprint。

**新增能力：**
- `src/blueprint.py`, `src/blueprint_export.py`, `src/text_safety.py` — Agent 系统蓝图生成/导出/安全
- `tests/test_blueprint.py`, `tests/test_config_safety.py`
- `frontend/src/components/Blueprint/`, `frontend/src/components/Preset/` — 新前端组件
- `docs/plans/2026-05-04-agent-preset-design.md`, `docs/plans/2026-05-05-preset-implementation-plan.md`
- `report/2026-05-04-mattpocock-skills-analysis.md`

## 1. 30 秒理解项目

`agora` 是已从 Semantic Kernel 主仓库拆出的**独立项目**，用来让多个 LLM agent 围绕一个议题进行有主持人控场的群组讨论 → 投票 → 报告归档。提供 CLI 和 Web UI 两种交互。

- **入口路径**：项目根目录
- **Semantic Kernel 依赖**：默认走 `pyproject.toml` 的 `semantic-kernel>=1.0.0`
- **Python 包名**：`agora`，源码在 `src/`
- **CLI**：`agora`（`src/cli.py:main`）
- **Web 后端**：`agora-web`（`src/web_entry.py:main` → `src/web_server.py`）
- **前端**：`frontend/`（Vite + React + TypeScript）

---

## 2. 关键文件地图

### 后端（`src/`）

| 文件 | 行数级别 | 你需要读它当且仅当 |
|---|---|---|
| `cli.py` | 小 | 修改 CLI 参数或入口流程 |
| `web_server.py` | ~620 | 修改 WebSocket 协议、会话生命周期、报告/会话 REST API |
| `pipeline.py` | 中 | 修改 CLI 端的 discussion → voting → save 流程 |
| `discussion.py` | ~390 | 修改 `LLMGroupChatManager`（选人/终止/总结策略） |
| `brainstorm.py` | 大（17KB） | 修改议题精炼阶段（`BrainstormSession` 状态机、降级策略） |
| `voting.py` | 中 | 修改投票逻辑或聚合规则 |
| `loader.py` | 小 | 修改 YAML 配置加载、agent 实例化、Kernel 注册 |
| `models.py` | 小 | 修改 Pydantic 配置模型（`AppConfig` / `BrainstormConfig` 等） |
| `openai_sse_proxy.py` | 中 | 修改对 SSE-only 本地代理的适配（streaming 路径有特殊处理） |
| `blueprint.py` | 中 | 修改 Agent 系统蓝图生成（含 fallback 机制） |
| `blueprint_export.py` | 小 | 修改蓝图导出格式（JSON/YAML/Markdown/Prompt Pack） |
| `reporting.py` | 小 | 修改最终 markdown 报告格式 |

### 前端（`frontend/src/`）

| 文件 | 你需要读它当且仅当 |
|---|---|
| `App.tsx` | 修改阶段路由（idle / brainstorming / discussion / voting / followup / saved） |
| `types.ts` | 修改 WS 事件类型、会话数据结构 |
| `hooks/useWebSocket.ts` | 修改 WS 事件处理 |
| `hooks/useSession.ts` | 修改会话状态管理 |
| `components/Timeline/VotingCard.tsx` | 修改投票卡片 UI |
| `components/Timeline/MessageBubble.tsx`（如有） | 修改消息气泡渲染 |
| `components/Progress/AgentStatusPanel.tsx` | 修改 agent 状态面板（含模型展示、主持人特殊样式） |

### 配置

- `src/config/agents.yaml` — 默认完整配置（含 8 个 agent + 6 种 preset + brainstorm/discussion/voting）
- `src/config/agents_optimized.yaml` — agents.yaml 优化变体（A/B test，仅覆盖差异项；新增 agent/preset 时需同步）
- `src/config/discussion_only.yaml` — 仅讨论
- `src/config/voting_only.yaml` — 仅投票
- `.env.example` — 本地环境变量模板，实际 `.env` 不纳入 Git

### 文档

- `README.md` — 用户向：安装、使用、配置、troubleshooting
- `KNOWN_ISSUES.md` — **本次会话发现的真实遗留问题清单**（必读）
- `docs/plans/2026-04-23-frontend-rebuild.md` — 前端重构设计
- `docs/plans/2026-04-24-moderator-brainstorm-design.md` — 主持人 brainstorm 设计 + 实施进度

---

## 3. 架构核心约束（绝对不能违反）

### 3.1 SK GroupChatOrchestration 的执行模型

`GroupChatOrchestration` 内部循环：

```
for round in range(max_rounds):
    if await manager.should_terminate(history):
        break
    next_agent = await manager.select_next_agent(...)
    await next_agent.invoke()
result = await manager.filter_results(history)  # 总结
```

**陷阱**：`should_terminate` 在第一轮（agent 还未发言时）就被调用。如果 LLM 此时判定 "应该结束"，**所有 agent 一句话都不会说，但 `filter_results` 仍会输出总结**——产生"无人发言但有结论"的怪现象。

**已部署的防御**：`LLMGroupChatManager.min_rounds` 字段 + `should_terminate` 的硬性守卫（见 `src/discussion.py:62, 118-129`）。`_run_managed_group_chat` 在调用时设置 `min_rounds = max(1, len(agents))`（见 `src/discussion.py:348`）。

### 3.2 SSE-only 代理的 streaming 适配

部分本地代理（`http://localhost:3030/v1`）只支持 SSE 流式，不支持非流式 `chat.completions.create`。但 SK 的 `GroupChatOrchestration` 内部会强制 `stream=True`。

**解决方案**：`src/openai_sse_proxy.py` 中的 `SSEProxyAsyncOpenAI` 实现了一个 `_PseudoAsyncStream`，并通过 `_OpenAIAsyncStream.register(_PseudoAsyncStream)` 注册为 `openai.AsyncStream` 的虚拟子类。SK 的 `isinstance(response, AsyncStream)` 检查会通过。

**改动 `openai_sse_proxy.py` 时务必保留**：
- `_PseudoAsyncStream` 的 `__aiter__` / `__anext__` 实现
- `_OpenAIAsyncStream.register(_PseudoAsyncStream)` 注册调用
- 兜底分支：当 caller 没传 `stream=True` 时仍走非流式路径

### 3.3 WebSocket 事件契约

| 方向 | type | 关键字段 |
|---|---|---|
| ← server | `phase` / `phase_changed` | `phase`, `label` |
| ← server | `message` | `phase`, `name`, `role`, `content` |
| ← server | `agent_status` | `name`, `state` |
| ← server | `voting_result` | `votes[]`, `conclusion` |
| ← server | `agent_meta` | `agents: [{name, model, role, is_moderator}]` |
| ← server | `blueprint` | `blueprint`, `warnings` |
| ← server | `moderator_question` | `round`, `question`, `options[]`, `allow_freetext`, `model` |
| → client | `moderator_answer` | `round`, `answer` |
| → client | `brainstorm_skip` | `{}` |
| ← server | `topic_refined` | `original`, `refined`, `context_summary?` |
| → client | `topic_confirmed` | `accept: true` |
| ← server | `brainstorm_timeout` | `{}` |

**`message` 事件的 name fallback 规则**（`web_server.py:170-184` + `:377-390`）：
- `role == 'user'` → `msg.name or "用户"`
- 其他 → `msg.name or "匿名"`

### 3.4 历史会话兼容

`sessions/*.json` 没有 `schema_version` 字段时视为 v1，回放时跳过 brainstorm 阶段。新会话写入时应带 `schema_version: 2`。

---

## 4. 修复记录汇总

### 2026-04-24 会话修复

> 以下修复已在 2026-04-25 验证通过，详见 `KNOWN_ISSUES.md` 已解决存档。

### 改动文件清单

| 文件 | 改动 | 状态 |
|---|---|---|
| `src/web_server.py` | `push_message` / `push_followup_msg` 按 role 区分 name fallback | ✅ 已修复 |
| `src/discussion.py` | `LLMGroupChatManager.min_rounds` 字段 + `should_terminate` 守卫 + `_run_managed_group_chat` 设置 floor | ✅ 已修复 |
| `src/discussion.py` | `on_agent_selected` 传入 `LLMGroupChatManager`，恢复被选中 agent 的 thinking 状态推送 | ✅ 单测通过 |
| `src/brainstorm.py` / `src/models.py` / `src/web_server.py` | 接入可见的主持人 brainstorm：Host 提问、复杂度判断、派发计划进入 `message` 流，并等待用户确认精炼议题 | ✅ 单测通过，待 UI 实测 |
| `frontend/src/hooks/useWebSocket.ts` / `frontend/src/App.tsx` / `frontend/src/components/Timeline/Timeline.tsx` | 接入 Opus 产出的 Brainstorm UI 组件与 HostMessage 渲染 | ✅ `npm run build` 通过 |
| `src/voting.py` | 投票 prompt 禁止 `<think>`，并清洗 reason 中的 `<think>...</think>` 块 | ✅ 单测通过 |
| `frontend/src/components/Timeline/VotingCard.tsx` | 重写为「统计条 + 子卡列表 + 强调 conclusion」 | ✅ 编译通过，待 UI 实测 |
| `frontend/src/components/Timeline/VotingCard.module.css` | 配套样式 | ✅ 同上 |

### 本次会话验证用的 session 文件

- `sessions/mocoj2ki.json` — 修复**前**的会话，暴露了三个原始问题
- `sessions/mobavn8e.json` — 修复**后**第一次回归测试，暴露修复未真正生效
- 下一次回归请新建一份 session 并对照 `KNOWN_ISSUES.md` 验收

### 2026-05-05 会话修复

本次修复源自 `docs/superpowers/plans/2026-05-05-multi-issue-fix.md` 计划，覆盖 10 个 UX 和功能缺陷。

| 文件 | 改动 | 状态 |
|---|---|---|
| `frontend/src/App.tsx:114-144` | sync effect 加 `!session.isHistoryMode` 守卫，修复会话列表标题被覆写 bug（#10） | ✅ 已修复 |
| `frontend/src/components/InputBar/InputBar.tsx` | `<input>` → `<textarea>` + 自动扩展高度 | ✅ 已修复 |
| `frontend/src/components/Timeline/Timeline.tsx:38` | `msg.meta?.variant` → `msg.meta?.variant !== undefined` 严格存在性检查 | ✅ 已修复 |
| `src/web_server.py::push_message` | host 消息附加 `meta: {variant: "normal"}` 让前端正确路由 | ✅ 已修复 |
| `frontend/src/components/Preset/PresetSelector.tsx` | agent 名映射为中文显示（Architect→架构师 等） | ✅ 已修复 |
| `src/config/agents.yaml` | Architect prompt 移除"三年后"表述；新增 `document_design` preset | ✅ 已修复 |
| `src/config/agents_optimized.yaml` | 同步 agents.yaml 全部变更 + 同步策略注释 | ✅ 已修复 |
| `src/blueprint.py` | fallback blueprint name → "本次讨论总览"；output_contract 写入 final_solution | ✅ 已修复 |
| `src/blueprint_export.py` | 新增 `_sanitize_filename` 清洗 markdown 链接语法 | ✅ 已修复 |
| `frontend/src/components/Blueprint/BlueprintPanel.tsx` | warnings 展示为 info 提示而非错误 | ✅ 已修复 |
| `src/reporting.py` | 报告结构重写：概述→讨论设置→方案详情→评审结论→讨论过程 | ✅ 已修复 |

---

## 5. 项目约定

### 命令

```bash
# 同时启前后端（本地开发）
./start.sh

# 单独启后端
agora-web

# CLI 模式
agora -t "你的议题"
agora -c src/config/discussion_only.yaml -t "议题" -v
```

### 代码风格

- Python：遵循 `mypy.ini` 和 `pyproject.toml`，不要引入新依赖前先确认 `pip install -e .` 仍能跑通
- 前端：CSS Modules（不用 Tailwind / styled-components），使用 `var(--xxx)` 设计变量
- 注释语言：中英文皆可，但 docstring 用英文

### 不要做的事

- ❌ 不要重写 `GroupChatOrchestration` —— 直接用并通过 `LLMGroupChatManager` 注入策略
- ❌ 不要在 `discussion.py` 里直接调 `service.client.chat.completions.create` —— 用 SK 提供的 `service.get_chat_message_content`
- ❌ 不要为当前项目修改外部 `semantic-kernel-main/python/semantic_kernel/` 代码 —— 所有适配应在 `agora/src/` 内完成
- ❌ 不要为 brainstorm 阶段设计模板库 —— 设计文档明确 YAGNI 否决
- ❌ 不要给 brainstorm 加多个主持人之间的反思循环 —— 同上

---

## 6. 当前进行中的工作

### 2026-05-05：10 项 UX/功能修复完成

已完成计划 `docs/superpowers/plans/2026-05-05-multi-issue-fix.md` 全部修复，包括：会话列表标题 bug（#10）、InputBar textarea、Timeline 渲染、Preset 中文名、Architect prompt、document_design preset、Blueprint fallback、导出路径清理、报告结构重写。

该批改动已进入收尾验证；后续维护以 `src/config/agents.yaml` 为权威配置，`agents_optimized.yaml` 只作为同步变体。

### 历史

参见：
- `docs/plans/2026-04-24-moderator-brainstorm-design.md` 末尾的「实施进度」章节
- `KNOWN_ISSUES.md` 中标记 `status: 🚧 进行中` 或 `📋 待办` 的条目

2026-04-25 已完成：
1. 项目迁移为独立仓库
2. 清理 `.omx` / `.omc` / `.claude` / 缓存 / 构建产物，保留 `docs/`、`report/`、`sessions/`
3. 默认配置改为环境变量读取 key，避免把本地密钥纳入 Git
4. 后端入口改为可安装模块 `src.web_entry:main`

---

## 🟢 低优先级（不阻塞主流程）

### #7 💡 IDE 报 `fastapi` / `semantic_kernel` "未解析的引用"

**状态**：环境问题，可忽略

JetBrains IDE 索引未识别 `pip install -e` 安装的包。**代码本身合法**，运行时没问题。

**消除方法**：在项目根目录执行 `pip install -e ".[dev]"`。

---

### #8 💡 README 文档并存清理

**状态**：✅ 已清理

当前只保留 `README.md`。

---

### #9 💡 投票阶段 conclusion 文案过于机械

**状态**：可优化

当前 `voting.py` 的 conclusion 形如 `"多数赞成（2 赞成 / 0 反对 / 1 中立）"`，纯靠数据生成。

**可优化方向**：让主持人 LLM 在投票后再生成一段自然语言总结，覆盖在 `conclusion` 字段。但要注意成本。

---

## 维护说明

新增一个问题时遵循模板：

```markdown
### #N 状态符号 一句话标题

**状态**：🚧 进行中 / 📋 待办 / ✅ 已修复 / ❌ 已确认无法修复

**现象**：（用户能感知到的具体表现，最好附带数据来源）

**根因**：（如已知）

**影响**：（不修会怎样）

**建议下一步**：（具体到文件 + 行号 + 操作）
```

状态符号：🔴 高 / 🟡 中 / 🟢 低 / 🚧 进行中 / 📋 待办 / ✅ 已修复 / ❌ 已确认无法修复 / ⚠️ 警告 / 💡 优化建议
