# KNOWN_ISSUES — Agent Discussion 问题记录

> 本文档记录已知问题和本轮修复记录。每个问题都附带：现象、根因（如已知）、影响、建议下一步或修复记录。
> 修复一项就把它从这里删除（同时更新 `CLAUDE.md` 的「修复记录」章节）。
>
> 最近一次扫描：2026-04-25（迁移到 `/Users/lvzhibo/Agent/agent-discussion` 后）

---

## 🔴 高优先级（影响主流程可用性）

### #1 ⚠️ `min_rounds` 守卫未真正生效，agent 仍被跳过发言

**状态**：✅ 已修复（2026-04-25）

**现象**：
- `sessions/mobavn8e.json` 显示 `discussion` 阶段只有 user → Host 总结 → Synthesizer 三条消息，**Architect / Pragmatist / Challenger 一句话都没说**
- 但投票阶段三个 agent 都正常输出了投票
- 这与本次会话已应用的 `min_rounds = max(1, len(agents))` 守卫预期完全不符

**根因**：
后端旧进程未 reload 是主要诱因；后续又发现 discussion timeout 时 `runtime.stop_when_idle()` 会等待异常 actor 导致流程卡住。

**影响**：
- 整个 discussion 阶段失去意义
- 用户投诉"主持人直接总结了"
- 投票结果失去"基于讨论"的前提

**修复记录**：
已启用 Web 后端 reload，增加派发绑定执行，并在 discussion timeout 时直接 `runtime.stop()`。`scripts/e2e_discussion_ws.py` 已跑通完整流程。

**关联代码**：
- `src/discussion.py:62`（`min_rounds` 字段定义）
- `src/discussion.py:118-129`（守卫逻辑）
- `src/discussion.py:348-352`（`min_rounds_floor` 设置）

---

### #2 ⚠️ user 消息 name 仍显示 "Unknown"

**状态**：✅ 已修复（2026-04-25）

**现象**：
- `sessions/mobavn8e.json` 中 `id=2`、`role="user"` 的消息 `name` 字段仍为 `"Unknown"`
- 本次会话已修改 `web_server.py::push_message`，按 role 区分 fallback（user → "用户"，其他 → "匿名"），但持久化数据显示未生效

**根因**：
与 #1 同类，后端旧进程未 reload 会导致 fallback 修复未生效。

**影响**：
- UI 显示不友好
- 但不影响功能

**修复记录**：
后端按 role 区分 fallback，用户消息显示为 `用户`，assistant 缺 name 时显示为 `匿名`。

**关联代码**：
- `src/web_server.py:170-184`（`push_message` 后端 fallback）
- `src/web_server.py:377-390`（`push_followup_msg` 后端 fallback）
- 可能的前端硬编码：`frontend/src/utils/session.ts`、`frontend/src/hooks/useSession.ts`

---

## 🟡 中优先级（影响完整性 / 可发现性）

### #4 📋 设计文档阶段 3 / 4 未完成（前端 Brainstorm UI）

**状态**：✅ 已修复（2026-04-25）

后端（阶段 2）`brainstorm.py` + `models.py::BrainstormConfig` + `web_server.py` 的 `wait_user_brainstorm_answer` / `pending_brainstorm_answers` 已落地。

**修复记录**：
前端已接入 `BrainstormPanel`、`TopicConfirmCard`、`BrainstormStates`，`useWebSocket.ts` 已处理 `moderator_question` / `topic_refined` / `brainstorm_timeout`。

---

### #5 📋 `agent_meta` 事件未推送，前端无法显示 agent 模型 / 主持人 badge

**状态**：✅ 已修复（2026-04-25）

设计文档定义了 `agent_meta` 事件（会话开始时一次性推送 `[{name, model, role, is_moderator}]`），早期后端未实现该推送。

**影响**：
- AC1.1 / AC1.2 / AC1.3 全部未满足
- 前端 `AgentStatusPanel` 即使加了 model 字段渲染逻辑也拿不到数据

**修复记录**：
`web_server.py::_run_session_pipeline` 已在会话开始推送 `agent_meta`，前端 `useWebSocket.ts` 已消费该事件。

---

### #6 📋 FastAPI 后端未启用 `--reload`，开发体验差

**状态**：✅ 已修复

`src/web_entry.py` 当前通过 `uvicorn.run(..., reload=True, reload_dirs=["src"])` 启动，`run_web.py` 只保留兼容入口。

**影响**：
- 每次改 `src/*.py` 都要手动 `Ctrl+C` 重启
- 用户改完代码以为"修好了"，但服务还是旧版

**验证**：`start.sh` 调用 `run_web.py`，后端实际入口为 `src.web_entry:main`。

---

## 🟢 低优先级（不阻塞主流程）

### #7 💡 IDE 报 `fastapi` / `semantic_kernel` "未解析的引用"

**状态**：环境问题，可忽略

JetBrains IDE 索引未识别 `pip install -e` 安装的包。**代码本身合法**，运行时没问题。

**消除方法**：在项目根目录执行 `pip install -e ".[dev]"`。如需调试本机 SK 源码，再执行 `pip install -e /Users/lvzhibo/Downloads/semantic-kernel-main/python`。

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

**状态**：🔴 高 / 🟡 中 / 🟢 低 / 🚧 进行中 / 📋 待办 / ✅ 已修复 / ❌ 已确认无法修复 / ⚠️ 警告

**现象**：（用户能感知到的具体表现，最好附带数据来源）

**根因**：（如已知）

**影响**：（不修会怎样）

**建议下一步**：（具体到文件 + 行号 + 操作）

**关联代码**：（文件:行号 列表）
```
