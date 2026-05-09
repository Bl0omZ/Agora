# Agora

## Overview

基于 Semantic Kernel 的多 LLM agent 群组讨论工具。多个不同模型/人设的 agent 围绕议题进行有主持人的讨论 → 投票 → 报告归档，提供 CLI 和 Web UI。
优先级：正确性 > 功能完整性 > UI 美化。

## Tech Stack

- **后端**：Python ≥ 3.10, semantic-kernel≥1.0, FastAPI≥0.110, Pydantic≥2.0, PyYAML≥6.0
- **前端**：Vite 6, React 18, TypeScript 5.6, CSS Modules（无 Tailwind / styled-components）
- **入口**：CLI `agora`（`src/cli.py`），Web 后端 `agora-web`（`src/web_entry.py` → `src/web_server.py`）

## 关键文件地图

| 文件 | 何时读 |
|------|--------|
| `src/discussion.py` | 修改 LLMGroupChatManager（选人/终止/总结策略） |
| `src/brainstorm.py` | 修改议题精炼状态机或降级策略 |
| `src/voting.py` | 修改投票逻辑或聚合规则 |
| `src/web_server.py` | 修改 WebSocket 协议、会话/报告/配置 REST API |
| `src/loader.py` | 修改 YAML 配置加载、agent 实例化 |
| `src/models.py` | 修改 Pydantic 配置模型 |
| `src/blueprint.py` | 修改 Agent 系统蓝图生成 |
| `src/blueprint_export.py` | 修改蓝图导出格式 |
| `src/config_writer.py` | 修改后端配置安全写入 |
| `src/openai_sse_proxy.py` | 修改 SSE-only 本地代理适配（streaming 路径特殊处理） |
| `src/pipeline.py` | 修改 CLI 端 discussion→voting→save 流程 |
| `src/reporting.py` | 修改 markdown 报告格式 |
| `frontend/src/App.tsx` | 修改阶段路由 |
| `frontend/src/types.ts` | 修改 WS 事件类型、会话数据结构 |
| `frontend/src/hooks/useWebSocket.ts` | 修改 WS 事件处理 |
| `frontend/src/hooks/useSession.ts` | 修改会话状态管理 |
| `frontend/src/hooks/useConfigApi.ts` | 修改配置编辑 API 调用 |
| `frontend/src/pages/SettingsPage.tsx` | 修改 Settings 页面布局 |
| `frontend/src/components/Summary/DiscussionSummaryDashboard.tsx` | 修改讨论总结仪表盘 |
| `frontend/src/components/Progress/AgentStatusPanel.tsx` | 修改 agent 状态面板 |

## 架构核心约束

### SK GroupChatOrchestration 陷阱

`should_terminate` 在第一轮 agent 发言前就被调用。如果 LLM 此时判定终止，所有 agent 不会发言但 `filter_results` 仍输出总结。
**防御**：`LLMGroupChatManager.min_rounds` + `should_terminate` 硬守卫（`discussion.py:62, 118-129`），运行时设 `min_rounds = max(1, len(agents))`（`discussion.py:348`）。

### SSE 代理 streaming 适配

`openai_sse_proxy.py` 的 `SSEProxyAsyncOpenAI` 用 `_PseudoAsyncStream` 注册为 `openai.AsyncStream` 虚拟子类，SK 的 isinstance 检查才能通过。改动此文件**务必保留** `__aiter__`/`__anext__` 实现、注册调用、非流式兜底分支。

### WebSocket 事件契约（关键事件）

| ← server | → client |
|----------|----------|
| `phase`, `message`, `agent_status`, `agent_meta` | `moderator_answer`, `brainstorm_skip`, `topic_confirmed` |
| `voting_result`, `blueprint`, `moderator_question` | |
| `topic_refined`, `brainstorm_timeout` | |

`message` 事件 name fallback：`role == 'user'` → `"用户"`，其他 → `"匿名"`。

### 会话格式

`sessions/*.json` 无 `schema_version` 视为 v1（跳过 brainstorm），新会话写 `schema_version: 2`。

## 命令

```bash
./start.sh              # 同时启动前后端
agora-web               # 仅后端
agora -t "议题"          # CLI 模式
agora -c config.yaml -t "议题" -v
python -m pytest ./tests/ -x -q   # 运行测试
cd frontend && npx tsc --noEmit    # 前端类型检查
```

## Do NOT introduce unless explicitly requested

- Tailwind / styled-components — 项目统一 CSS Modules + `var(--xxx)` 设计变量
- 新 Python 依赖 — 先确认 `pip install -e ".[dev]"` 仍通过
- 重写 `GroupChatOrchestration` — 通过 `LLMGroupChatManager` 注入策略
- 在 `discussion.py` 直接调 `chat.completions.create` — 用 SK 的 `service.get_chat_message_content`
- 修改外部 `semantic-kernel/` 代码 — 所有适配在 `agora/src/` 内完成
- Brainstorm 模板库 / 多主持人反思循环 — YAGNI

## Coding Rules

- Python：遵循 `pyproject.toml` 和 `mypy.ini`，docstring 用英文
- 前端：CSS Modules，设计变量 `var(--xxx)`，禁止 `any` 类型
- 破坏性操作前必须确认（`force push`、`git reset --hard`、`DROP TABLE` 等）
- 变更后运行测试套件和 TypeScript 检查，验证通过才算完成

## Working Style

- 不确定时先提问，不默认选择
- 存在更简单方案时主动提出
- 最小改动原则，不引入无关抽象
- 匹配现有代码风格
- 多步骤任务先列计划再执行

## Pointers

- 设计文档：`docs/plans/`
- UI 规范：`docs/ui-spec/design-spec.md`
- 遗留问题：`KNOWN_ISSUES.md`
- 用户文档：`README.md`