# KNOWN_ISSUES — Agent Discussion 问题记录

> 本文档记录已知问题和本轮修复记录。每个问题都附带：现象、根因（如已知）、影响、建议下一步或修复记录。
> 修复一项就把它从这里删除（同时更新 `CLAUDE.md` 的「修复记录」章节）。
>
> 最近一次扫描：2026-05-05（合并前收尾）

---

## 🔴 高优先级（影响主流程可用性）

（当前无未解决的高优问题）

---

## 🟡 中优先级（影响完整性 / 可发现性）

（当前无未解决的中优问题）

---

## 🟢 低优先级（不阻塞主流程）

### #7 💡 IDE 报 `fastapi` / `semantic_kernel` "未解析的引用"

**状态**：环境问题，可忽略

JetBrains IDE 索引未识别 `pip install -e` 安装的包。**代码本身合法**，运行时没问题。

**消除方法**：在项目根目录执行 `pip install -e ".[dev]"`。如需调试本机 SK 源码，再执行 `pip install -e /Users/lvzhibo/Downloads/semantic-kernel-main/python`。

---

### #9 💡 投票阶段 conclusion 文案过于机械

**状态**：可优化

当前 `voting.py` 的 conclusion 形如 `"多数赞成（2 赞成 / 0 反对 / 1 中立）"`，纯靠数据生成。

**可优化方向**：让主持人 LLM 在投票后再生成一段自然语言总结，覆盖在 `conclusion` 字段。但要注意成本。

---

## ✅ 已解决（存档）

以下问题已在各阶段修复，保留在此供回溯。

### #1 ✅ `min_rounds` 守卫未真正生效

**修复日期**：2026-04-25

**现象**：discussion 阶段 agent 被跳过发言，主持人直接总结。

**修复**：启用 Web 后端 reload，增加派发绑定执行，discussion timeout 直接 `runtime.stop()`。

**关联代码**：`src/discussion.py:62`, `:118-129`, `:348-352`

---

### #2 ✅ user 消息 name 仍显示 "Unknown"

**修复日期**：2026-04-25

**现象**：`role="user"` 的消息 `name` 字段为 `"Unknown"`。

**修复**：后端按 role 区分 fallback（user → "用户"，assistant → "匿名"）。

**关联代码**：`src/web_server.py:170-184`, `:377-390`

---

### #4 ✅ 设计文档阶段 3 / 4 未完成（前端 Brainstorm UI）

**修复日期**：2026-04-25

**修复**：前端已接入 `BrainstormPanel`、`TopicConfirmCard`、`BrainstormStates`，`useWebSocket.ts` 已处理相关事件。

---

### #5 ✅ `agent_meta` 事件未推送

**修复日期**：2026-04-25

**修复**：`web_server.py::_run_session_pipeline` 已在会话开始推送 `agent_meta`，前端已消费该事件。

---

### #6 ✅ FastAPI 后端未启用 `--reload`

**修复日期**：2026-04-25

**修复**：`src/web_entry.py` 通过 `uvicorn.run(..., reload=True, reload_dirs=["src"])` 启动。

---

### #8 ✅ README 文档并存清理

**修复日期**：2026-04-25

**修复**：当前只保留 `README.md`。

---

### #10 ✅ 会话列表点击后标题全变

**修复日期**：2026-05-05

**现象**：在 Web UI 中，点击侧边栏会话列表中的任意一条历史会话后，所有会话标题变成错误的值。

**根因**：`App.tsx` 的 sync effect（lines 114-144）在 `ws.isReady` 为 true 时，用 live discussion 的 topic 覆盖服务端历史会话文件。

**修复**：在 sync effect 中增加 `!session.isHistoryMode` 守卫，防止历史会话被覆盖写入。

**关联代码**：`frontend/src/App.tsx:114-144`

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
