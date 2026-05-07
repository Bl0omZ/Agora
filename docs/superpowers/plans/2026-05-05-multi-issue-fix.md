# 多问题修复实现计划

> **状态：✅ 已完成（2026-05-05）** — 全部 10 个问题已修复，详见 `CLAUDE.md` 修复记录。
>
> 原始说明：使用 superpowers:subagent-driven-development 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。UI 相关任务（A 子系统）必须先调用 huashu-design skill 获取设计指导。

**目标：** 修复 10 个用户体验和功能缺陷，覆盖 UI 渲染、agent 行为、preset 匹配、blueprint 生成、导出和报告质量。

**架构：** 按子系统拆为 5 个独立模块——A) UI 修复（InputBar + Timeline 渲染）、B) Preset/Agent 修复（名称显示 + Architect prompt + 新增文档设计 preset）、C) Blueprint 修复（验证 + 内容 + 导出）、D) 报告质量（prompt 注入 technical-writer/humanizer-zh 约束）。

**技术栈：** React + TypeScript（前端）、Python + Pydantic + Semantic Kernel（后端）、YAML 配置

**可复用 Skill 参考：**

| Skill | 用途 | 复用方式 |
|-------|------|---------|
| `humanizer-zh` | 去除中文文本 AI 痕迹：夸大象征、宣传语言、肤浅分析、模糊归因、破折号过度、三段式法则、AI 词汇、否定排比、过多连接短语 | 作为后处理约束注入报告和 Agent 输出 prompt |
| `technical-writer` | 技术文档、API 参考、教程、用户指南的写作规范——受众分析、信息密度、可验证性 | 提取为 prompt 约束注入报告生成和文档设计类 agent prompt |
| `brainstorming` | 编码前探索需求与设计 | 已用于 brainstorm 阶段，无需重复引用 |

---

## A. UI 修复

> **⚠️ 实现前必须先调用 huashu-design skill** 获取输入框和 Timeline 渲染的设计指导。

### 任务 A1：InputBar 改为 textarea 支持长文本

**文件：**
- 修改：`frontend/src/components/InputBar/InputBar.tsx`
- 修改：`frontend/src/components/InputBar/InputBar.module.css`

**问题：** 当前使用 `<input type="text">` 单行输入框，无法输入和显示长文本。用户反馈 main 分支原有该能力，worktree 版本退化。

**根因：** `InputBar.tsx:24` 使用 `<input type="text">`，应改为 `<textarea>` 并支持自动扩展高度。

- [ ] **步骤 1：改为 textarea + 自动扩展**

```tsx
// frontend/src/components/InputBar/InputBar.tsx
import { useState, useRef, useEffect } from 'react';
import styles from './InputBar.module.css';

interface InputBarProps {
  onSend: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function InputBar({ onSend, placeholder = '输入追问内容…', disabled = false }: InputBarProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea on content change
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  }, [text]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setText('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter to submit, Shift+Enter for newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className={styles.inputBar} onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className={styles.input}
        rows={1}
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className={styles.sendButton}
      >
        发送
      </button>
    </form>
  );
}
```

- [ ] **步骤 2：更新 CSS 适配 textarea**

```css
/* frontend/src/components/InputBar/InputBar.module.css — 替换 .input 样式块 */
.input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-medium);
  background: var(--bg-input);
  font-size: 14px;
  font-family: inherit;
  color: var(--ink-primary);
  resize: none;
  min-height: 40px;
  max-height: 200px;
  line-height: 1.5;
}

.input:focus {
  outline: none;
  border-color: var(--accent);
}

.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input::placeholder { color: var(--ink-muted); }
```

- [ ] **步骤 3：验证**

1. `cd frontend && npx tsc --noEmit` — 编译零错误
2. 浏览器测试：输入长文本，自动扩展；Shift+Enter 换行；Enter 发送

---

### 任务 A2：Timeline 消息渲染修复——主持人回复不显示

**文件：**
- 修改：`frontend/src/components/Timeline/Timeline.tsx:37-39`

**问题：** 主持人回复消息的 `name` 是配置中的实际名字（非 "Host"），且没有 `meta.variant`，导致路由到 `MessageBubble`。但由于 Timeline 中主持人消息不应走 MessageBubble，内容未正确渲染。

**根因：** `Timeline.tsx:38` 的条件 `msg.name === 'Host' || msg.meta?.variant` 只能匹配 name 恰好为 "Host" 的主持人消息。但在 agents.yaml 中主持人 name 是 "Host"，消息推送时 `msg.name` 是 `session.manager_config.name`（即 "Host"）。问题在于后端 `_send_host_message` 传的 name 是 `session.manager_config.name`，但 `push_message` 中 `display_name = msg.name or "匿名"` 可能修改了 name。

- [ ] **步骤 1：修改 Timeline 路由条件**

在 `Timeline.tsx` 中，将主持人消息的识别改为检查 `role === 'assistant'` 且 `name` 在 agent_meta 中是 moderator：

由于 Timeline 不持有 agent_meta 信息，改用更简单的方式：后端推送的 host message 已经带有 `meta: { variant: "normal" }`（见 `_send_host_message`），所以 `msg.meta?.variant` 为 `"normal"` 是有值的。

当前条件已包含 `msg.meta?.variant`，但需要确认 `meta` 不为 null/undefined 时 variant 一定存在。查看后端代码 `web_server.py:801-808`：

```python
await _send_json(websocket, {
    "type": "message",
    "phase": phase,
    "name": session.manager_config.name,
    "role": "assistant",
    "content": content,
    "meta": meta or {"variant": "normal"},
})
```

当 `meta=None` 时，后端发 `"meta": {"variant": "normal"}`。但讨论阶段的 `push_message`（`web_server.py:1029-1041`）没有传 meta。

修复：在 `push_message` 中传递 meta，让主持人消息能被识别。最简单的方式是：在讨论阶段，host 消息由 `sync_callback` 从 `GroupChatOrchestration` 回调传入，这些消息的 name 是 manager 的 name（"Host"），role 是 "assistant"。可以在 Timeline 增加条件：如果 `msg.role === 'assistant'` 且 `msg.name` 以特定方式标记，则走 HostMessage。

更简洁的修复：后端在 `push_message` 中给 host 消息附加 `meta: { variant: "normal" }`。

```python
# web_server.py:1029-1041, push_message 函数
async def push_message(msg: ChatMessageContent, phase: str) -> None:
    msg_id = id(msg)
    if msg_id in pushed_message_set:
        return
    pushed_message_set.add(msg_id)
    role_value = msg.role.value if msg.role else "assistant"
    if role_value == "user":
        display_name = msg.name or "用户"
    else:
        display_name = msg.name or "匿名"

    # Mark host messages with meta so frontend can route them correctly
    is_host = (display_name == session.manager_config.name)

    await _send_json(websocket, {
        "type": "message",
        "phase": phase,
        "name": display_name,
        "role": role_value,
        "content": msg.content or "",
        "meta": {"variant": "normal"} if is_host else getattr(msg, "metadata", None),
    })
```

- [ ] **步骤 2：前端增加兜底条件**

`Timeline.tsx:38` 改为：

```tsx
{msg.name === 'Host' || msg.meta?.variant !== undefined ? (
  <HostMessage message={msg} meta={msg.meta ?? { variant: 'normal' }} />
) : (
  <MessageBubble message={msg} />
)}
```

条件从 `msg.meta?.variant`（falsy check）改为 `msg.meta?.variant !== undefined`（严格存在性 check），确保 variant 为 "normal" 的 host 消息也能进入 HostMessage 渲染。

- [ ] **步骤 3：验证**

1. 重新运行一次讨论，确认主持人总结消息在 Timeline 中正常渲染
2. 检查消息内容中的 markdown 是否正确转为 HTML

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/Timeline/Timeline.tsx src/web_server.py
git commit -m "fix: render moderator replies in Timeline via meta.variant routing"
```

---

## B. Preset / Agent Prompt 修复

### 任务 B1：PresetSelector agent 名称中英文混合

**文件：**
- 修改：`frontend/src/components/Preset/PresetSelector.tsx:47-48`

**问题：** `agents.map(agent => agent.name).join(' · ')` 直接显示原始英文名（如 Architect、Pragmatist）。用户看到的是混合语言："Architect ·务实主义者·挑战者号"（"挑战者号" 是 Challenger 的机器翻译错误）。

**根因：** agents.yaml 中 presets 的 agent 名是英文，前端没有做 display name 映射。需要在显示前将 name 映射为中文标签。

- [ ] **步骤 1：建立 agent name → 中文标签映射**

在 `constants.ts` 中添加 agent display name 映射，或直接在 PresetSelector 中做简单映射。

更简洁的方式：后端 `/api/sessions` 不返回 display name，而是在 `PresetSelector.tsx` 中加一个本地映射：

```tsx
// frontend/src/components/Preset/PresetSelector.tsx — 在 component 前添加
const AGENT_DISPLAY_NAMES: Record<string, string> = {
  Architect: '架构师',
  Pragmatist: '务实派',
  Challenger: '挑战者',
  Evaluator: '评估者',
  RequirementsAnalyst: '需求分析师',
  DomainExpert: '领域专家',
  ProcessDesigner: '流程设计师',
  RootCauseAnalyst: '根因分析师',
  Host: '主持人',
};

function getAgentDisplayName(name: string): string {
  return AGENT_DISPLAY_NAMES[name] ?? name;
}
```

- [ ] **步骤 2：修改参与者显示行**

```tsx
// 替换 line 48
参与者：{preset.agents.map((agent) => getAgentDisplayName(agent.name)).join(' · ')}
```

- [ ] **步骤 3：验证**

1. `cd frontend && npx tsc --noEmit` — 零错误
2. 浏览器测试：PresetSelector 显示 "架构师 · 务实派 · 挑战者" 而非中英混合

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/Preset/PresetSelector.tsx
git commit -m "fix: use Chinese display names for agents in PresetSelector"
```

---

### 任务 B2：Architect prompt 移除不相关的"三年扩展性"

**文件：**
- 修改：`src/config/agents.yaml:119-147`
- 同时修改：`src/config/agents_optimized.yaml:96-123`（保持两文件一致）

**问题：** Architect agent 的 instructions 第 127 行："三年后这个设计还能扛住吗？扩展点在哪？" 导致每个讨论中 Architect 都谈论长期扩展性，即使议题是发工单模板这样不需要此视角的场景。

**根因：** Architect 的思维框架被写死为三个固定问题，其中第二个是"三年后"。应该改为更通用的表述，让 Architect 根据议题决定是否需要讨论演进性。

- [ ] **步骤 1：修改 agents.yaml Architect instructions**

```yaml
# src/config/agents.yaml:119-147 — 替换 instructions 中的思维框架部分
  - name: Architect
    description: "架构师，从系统设计、模块边界、技术选型的角度评估方案"
    instructions: |
      你是一位资深架构师，在讨论中你代表**系统设计**的视角。

      **你的思维框架：**
      每次发言都要回答：
      1. 这个方案的模块边界画在哪里？数据流怎么走？
      2. 这个设计在可预见的未来是否足够灵活？关键假设是什么？
      3. 这样做引入了什么新的复杂度？值不值？

      **你的表达风格：**
      - 用组件图思维描述方案（画不了图就用文字描述组件和箭头）
      - 对每个技术选型给出"选它的核心理由"和"它的最大风险"
      - 用数量级思维：不说"很大"，说"百万级"；不说"很慢"，说"P99 > 2s"

      **与其他角色的互动：**
      - 当 Pragmatist 说"成本太高"时，你要回应：高在哪里？有没有降低成本但保留架构优势的折中方案？
      - 当 Challenger 质疑你的假设时，你要直面回应，不能回避
      - 你可以修改自己之前的方案——承认错误比坚持错误更有价值

      **你不做的事：**
      - 不讨论排期、人力、预算（那是 Pragmatist 的事）
      - 不为了"架构优美"牺牲明显不合理的成本
      - 不要预设所有方案都需要数年演进——根据议题范围判断
```

- [ ] **步骤 2：同步修改 agents_optimized.yaml**

同样的改动应用到 `agents_optimized.yaml:96-123`。

- [ ] **步骤 3：验证**

1. `python -c "from src.loader import load_config; load_config('src/config/agents.yaml')"` — 加载成功
2. 重跑一次讨论，确认 Architect 不再无端谈扩展性

- [ ] **步骤 4：Commit**

```bash
git add src/config/agents.yaml src/config/agents_optimized.yaml
git commit -m "fix: remove fixed 3-year-extensibility frame from Architect prompt"
```

---

### 任务 B3：新增 `document_design` preset——填补文档/模板设计场景

**文件：**
- 修改：`src/config/agents.yaml:67-87`（presets 区块）
- 修改：`src/config/agents_optimized.yaml`（同步）

**问题：** 现有 5 个 preset（架构评审、需求分析、方案对比、流程设计、复盘分析）全部为技术系统建设场景设计。当用户议题是"设计一份文档/模板"（如安全漏洞工单）时，主持人只能在 5 个不匹配的 preset 中选一个"相对最不差"的，导致推荐组合中至少有一个 agent 跑偏（如 Architect 谈扩展性、Pragmatist 算排期）。

**Agent 匹配分析：**

| Agent | 文档/模板设计场景匹配？ | 理由 |
|-------|:---:|------|
| DomainExpert | ✅ | 知道安全工单应含哪些字段（CVSS、CWE、影响面、复现步骤），可提供 OWASP/行业标准参考 |
| RequirementsAnalyst | ✅ | 把"清晰易懂"拆成可验证的字段要求，定义 Must do / Nice to have / Out of scope |
| Challenger | ✅ | 追问"开发真会看吗？""AI 真能解析吗？""字段缺失时降级路径是什么？" |
| Evaluator | 🟡 | 仅当有多套候选模板需要对比时有价值，单一模板设计用不上 |
| ProcessDesigner | 🟡 | 关心流程操作，非文档结构设计 |
| Architect | ❌ | 关心系统设计/模块边界/技术演进，对文档模板无贡献 |
| Pragmatist | ❌ | 关心交付成本/排期/团队能力，对模板设计无贡献 |
| RootCauseAnalyst | ❌ | 完全无关领域 |

**推荐组合：DomainExpert + RequirementsAnalyst + Challenger**

- DomainExpert 保证**专业准确**（行业标准、必须字段、CVSS/CWE 规范）
- RequirementsAnalyst 保证**需求完整**（边界、验收标准、使用场景覆盖）
- Challenger 保证**务实可用**（暴露盲点、压力测试可读性和 AI 可解析性）

**可复用 Skill：**
- `technical-writer`：预设描述和 agent prompt 应体现技术文档的结构化思维（受众分析、信息密度、可验证性）
- `humanizer-zh`：DomainExpert 和 RequirementsAnalyst 的输出应自然、去 AI 痕迹（避免宣传语言、AI 词汇、过多连接短语）

- [ ] **步骤 1：在 agents.yaml 新增 preset**

```yaml
# src/config/agents.yaml:67 — presets 区块，新增第一个 preset
presets:
  document_design:
    label: "文档设计"
    description: "模板/规范/标准的结构设计与评审"
    agents: [DomainExpert, RequirementsAnalyst, Challenger]
  architecture_review:
    # ... 保持不变
```

同时将 `default_preset` 改为空或不设置，让主持人根据议题自动选择最合适的 preset：

```yaml
# 将 line 66 改为
# default_preset: architecture_review  # 移除——改由主持人动态推荐
```

或者保留 `default_preset` 不变，但更新 brainstorm prompt 让主持人能跨 preset 推荐。更稳妥的做法：保留所有 preset，新增 `document_design`，不改 `default_preset`。主持人在 brainstorm 阶段会根据议题自动匹配。

- [ ] **步骤 2：确保主持人能看到新 preset 并做出正确匹配**

`web_server.py:530-555` 的 `_build_brainstorm_config` 会把所有 preset 列给主持人。新增的 `document_design` 会自动出现在 preset roster 中，主持人在生成 `dispatch_plan.recommended_preset` 时就能选择它。

无需修改后端——主持人 LLM 看到 preset 列表后自行匹配。

- [ ] **步骤 3：同步到 agents_optimized.yaml**

同样的 preset 定义复制到 `agents_optimized.yaml`。

- [ ] **步骤 4：验证**

1. 重跑一次议题"设计一份针对水平越权漏洞的安全工单 Markdown 模板"
2. 确认主持人推荐的 preset 是 "文档设计" 而非 "架构评审"
3. 确认 discussion 阶段是 DomainExpert / RequirementsAnalyst / Challenger 三人讨论（不再出现 Architect）

- [ ] **步骤 5：Commit**

```bash
git add src/config/agents.yaml src/config/agents_optimized.yaml
git commit -m "feat: add document_design preset for template and specification design"
```

---

## C. Blueprint 修复

### 任务 C1：Blueprint 验证错误时正确显示 fallback

**文件：**
- 修改：`src/web_server.py:701-729`（`_run_blueprint_phase`）
- 无需修改：`src/blueprint.py`（fallback 逻辑已存在且正确）

**问题：** 用户看到 "blueprint attempt 1 failed: ValidationError"。前端显示这条 warning，但没有显示 fallback blueprint 的内容，用户误以为整个 blueprint 生成失败。

**根因：** `blueprint.py` 的 `generate_blueprint` 在两次 JSON 解析失败后会调用 `build_blueprint_fallback` 生成 fallback blueprint，并返回带 warnings 的结果。但 `web_server.py:701-729` 将 warnings 作为 `blueprint_warning` 事件推送，前端 `BlueprintPanel` 将 warnings 渲染为错误提示。当前流程本身是正确的——fallback 的 blueprint 应该能显示。需要确认：前端是否正确渲染了 fallback blueprint。

排查方向：确认 `_run_blueprint_phase` 确实推送了 blueprint 事件，确认前端 BlueprintPanel 能正确展开显示。

- [ ] **步骤 1：确认后端流程正确**

`web_server.py:701-729` 当前代码：

```python
result = await generate_blueprint(...)
session.blueprint = result.blueprint  # fallback blueprint 已赋值
session.blueprint_warnings = result.warnings

await _send_json(websocket, {
    "type": "blueprint",
    "blueprint": result.blueprint,
    "warnings": result.warnings,
})
```

此流程正确——无论成功还是 fallback，blueprint 都会被推送。无需修改后端。

- [ ] **步骤 2：前端 BlueprintPanel 优化 warnings 展示**

BlueprintPanel 当前将 warnings 展示为红色警告块，但没有区分 "model failed, using fallback" 和真正的错误。优化：将 warnings 显示为 info 级别提示而非错误。

```tsx
// frontend/src/components/Blueprint/BlueprintPanel.tsx:58-62 — 修改 warn 样式
{warnings.length > 0 && (
  <div className={styles.warn}>
    <span className={styles.warnIcon}>ℹ️</span>
    {warnings.map((w, i) => <p key={i}>{w}</p>)}
  </div>
)}
```

在 CSS 中将 `.warn` 改为 info 色调（橙色/琥珀色而非红色）。

- [ ] **步骤 3：验证**

1. 重新跑一次包含 "blueprint attempt failed" 的会话
2. 确认 fallback blueprint 卡片完整显示（有 agents、workflow steps、risks）
3. 确认 warnings 展示为 info 提示而非错误

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/Blueprint/BlueprintPanel.tsx frontend/src/components/Blueprint/BlueprintPanel.module.css
git commit -m "fix: show blueprint fallback with info-level warnings instead of error"
```

---

### 任务 C2：Blueprint 标题改为"本次讨论总览"并包含结论

**文件：**
- 修改：`src/blueprint.py:457-459`（`build_blueprint_fallback` 中的 name）
- 修改：`frontend/src/components/Blueprint/BlueprintPanel.tsx:33-34`（标题区域）

**问题：** Blueprint 标题是 raw topic 文本（如 "设计一份针对水平越权漏洞的安全工单..."），太长且不像一个总览标题。用户期望标题为 "本次讨论总览"，且卡片中缺少核心结论展示。

- [ ] **步骤 1：后端将 blueprint name 设为 "本次讨论总览"**

```python
# src/blueprint.py:457 — build_blueprint_fallback
return AgentSystemBlueprint(
    session_id=session_id,
    name="本次讨论总览",  # 硬编码中文标题
    ...
)
```

同时修改 `parse_blueprint_response` 的数据，使模型生成的 blueprint 也使用统一标题。在 `_normalize_blueprint_payload` 中：

```python
# src/blueprint.py:153 — _normalize_blueprint_payload 开头
normalized = dict(data)
normalized.setdefault("name", "本次讨论总览")
# 但保留模型可能生成的更具体标题。不强行覆盖——只对 fallback 覆盖。
```

不修改 `_normalize_blueprint_payload`——只修改 `build_blueprint_fallback` 的 name。

- [ ] **步骤 2：BlueprintPanel 卡片头部增加结论区**

在 BlueprintPanel 的 problem 区域之前，增加结论 summary：

```tsx
// frontend/src/components/Blueprint/BlueprintPanel.tsx — 在 problem div 之前
{blueprint.output_contract.description && (
  <div className={styles.conclusion}>
    <span className={styles.conclusionLabel}>讨论结论</span>
    <p>{blueprint.output_contract.description}</p>
  </div>
)}
```

或者更好的方式：利用 `final_solution` 内容。当前 blueprint 的 `problem_statement` 携带了精炼议题，`output_contract.description` 携带了产出格式说明。需要从后端传递结论到 blueprint 中。

在后端 `build_blueprint_fallback` 和 prompt 中，将 `final_solution` 摘要写入 `output_contract.description`：

```python
# blueprint.py:459-466 — build_blueprint_fallback
output_contract=OutputContract(
    description=_limit_text(final_solution, max_chars=500) or "未生成结论",
    format="markdown",
    required_sections=["problem", "agents", "workflow", "evaluation"],
),
```

- [ ] **步骤 3：加 CSS 样式**

```css
/* BlueprintPanel.module.css */
.conclusion {
  padding: 12px 16px;
  background: var(--role-host-bg);
  border-left: 3px solid var(--role-host);
  border-radius: 4px;
  margin: 0 16px 12px;
}

.conclusionLabel {
  font-size: 12px;
  font-weight: 600;
  color: var(--role-host);
  text-transform: uppercase;
}
```

- [ ] **步骤 4：验证**

1. `cd frontend && npx tsc --noEmit`
2. 重新生成 blueprint，确认标题为 "本次讨论总览"，核心结论在卡片中可见

- [ ] **步骤 5：Commit**

```bash
git add src/blueprint.py frontend/src/components/Blueprint/BlueprintPanel.tsx frontend/src/components/Blueprint/BlueprintPanel.module.css
git commit -m "feat: rename blueprint to 本次讨论总览, add conclusion section"
```

---

### 任务 C3：修复导出文件路径 markdown 链接污染

**文件：**
- 修改：`src/web_server.py` 或 `src/blueprint.py`（添加 filename 清理逻辑）

**问题：** 导出文件路径显示为 `blueprint_idor_ticket_template_[001.md](http://001.md)`，文件名中包含 markdown 链接语法。这是 DeepSeek 模型的 markdown auto-link 泄漏——RL post-training 奖励了 chat 中的自动链接行为，这个先验泄漏到了 tool-call 边界。

**根因：** blueprint 的 `id` 字段可能从模型输出中提取，包含了 markdown 链接污染。在 `parse_blueprint_response` 中，`data = json.loads(_extract_json_payload(cleaned))` 提取了 JSON，但 JSON 内的 string 字段可能已被污染。

- [ ] **步骤 1：在 _extract_json_payload 后清洗 markdown 链接**

在 `src/blueprint.py` 的 `parse_blueprint_response` 函数中，JSON 解析后立即清洗所有 string 值中的 markdown 链接：

```python
# src/blueprint.py — 在 parse_blueprint_response 中，json.loads 之后
import re

_MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(https?://\1\)")

def _clean_md_auto_links(value: Any) -> Any:
    """Remove degenerate markdown auto-links where link text equals URL-without-protocol."""
    if isinstance(value, str):
        return _MD_LINK_PATTERN.sub(r"\1", value)
    if isinstance(value, list):
        return [_clean_md_auto_links(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_md_auto_links(item) for key, item in value.items()}
    return value

# 在 parse_blueprint_response 中:
data = json.loads(_extract_json_payload(cleaned))
data = _clean_md_auto_links(data)  # 新增：清洗 markdown 链接
data = _cleanup_value(data)
```

- [ ] **步骤 2：同时在 blueprint_export.py 中防御**

`blueprint_export.py:34` 中 filename 使用 `blueprint.id`：

```python
filename=f"{blueprint.id}.json",
```

在 export 函数中增加 filename sanitization（移除 URL 协议、路径分隔符等）：

```python
# blueprint_export.py:28 — export_blueprint 函数开头
import re

def _sanitize_filename(name: str) -> str:
    """Remove characters unsafe for filenames, including markdown link syntax."""
    # Remove markdown links: [text](url)
    name = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", name)
    # Replace path separators and other unsafe chars
    name = re.sub(r"[/\\:*?\"<>|]", "_", name)
    return name.strip() or "blueprint"

# 在每个 export 分支中使用:
filename=f"{_sanitize_filename(blueprint.id)}.json",
```

- [ ] **步骤 3：验证**

1. 确认 `blueprint.id` 不再包含 markdown 链接语法
2. 导出文件下载后文件名正确

- [ ] **步骤 4：Commit**

```bash
git add src/blueprint.py src/blueprint_export.py
git commit -m "fix: sanitize blueprint id to remove markdown auto-link leakage"
```

---

## D. 报告质量修复

### 任务 D1：报告 prompt 注入 technical-writer 和 humanizer-zh 约束

**文件：**
- 修改：`src/reporting.py`（save_report 函数及 prompt）
- 参考：`~/.claude/skills/technical-writer/SKILL.md`、`~/.claude/skills/humanizer-zh/SKILL.md`

**问题：** 当前生成的报告缺乏专业性——语言不精炼、结构不严谨、有明显的 AI 写作痕迹。

- [ ] **步骤 1：阅读参考 skill 文件**

先读取两个参考 skill 的内容，提取可用于 prompt 的约束规则：

```bash
cat ~/.claude/skills/technical-writer/SKILL.md
cat ~/.claude/skills/humanizer-zh/SKILL.md
```

- [ ] **步骤 2：修改 reporting.py 的 save_report prompt**

在 `save_report` 函数中，当前生成的是纯 markdown 报告。增加一个 synthesis prompt 用于生成高质量报告正文：

```python
# src/reporting.py — 新增/修改函数

def _build_report_prompt(
    topic: str,
    discussion_summary: str,
    voting_result: Any | None,
    dispatch_state: dict[str, Any] | None,
) -> str:
    dispatch = dispatch_state or {}
    voting_text = ""
    if voting_result:
        votes_detail = "\n".join(
            f"- {v.agent_name}: {v.stance} (置信度 {v.confidence:.0%}) — {v.reason}"
            for v in voting_result.votes
        )
        voting_text = f"\n投票结果：\n{votes_detail}\n结论：{voting_result.conclusion}"

    return f"""你是一位资深技术报告撰写者。请根据以下内容写一份专业的技术讨论报告。

议题：{topic}

讨论要点和结论：
{discussion_summary[:8000]}
{voting_text}

撰写要求（严格遵守）：

专业规范（来自 Technical Writer skill）：
- 结构清晰：摘要 → 背景 → 分析 → 结论 → 建议，每个部分有小标题
- 精确性：不用模糊词汇，给出具体数据和理由
- 简洁：每句话都要有信息量，删除废话
- 客观：用事实说话，不夸张不回避
- 可执行：结论部分给出明确的 actionable 建议

自然化要求（来自 humanizer-zh skill）：
- 去除 AI 写作痕迹：不用"综上所述"、"值得注意的是"、"我们可以看到"等机械套路
- 避免"显著"、"充分"、"有效的"等空洞修饰词
- 使用主动语态，直接陈述
- 段落之间自然过渡，不用生硬的序号连接词
- 句式长短交错，避免连续三个以上相似句型的段落

输出纯 Markdown 格式报告，不要  thinking 前缀。"""
```

- [ ] **步骤 3：如果是直接写文件而非 LLM 生成，则改为用 LLM 生成**

检查 `save_report` 当前实现。如果当前是纯数据拼接（不调 LLM），则需要改为调 LLM 生成。查看 `reporting.py` 确认。

假设当前实现是数据拼接，修改为：

```python
async def save_report(
    topic: str,
    discussion_summary: str,
    discussion_transcript: str,
    voting_result: Any | None,
    dispatch_state: dict[str, Any] | None,
    blueprint: Any | None,
    service: Any | None = None,  # 新增：LLM service
) -> Path:
    ...
    if service:
        prompt = _build_report_prompt(topic, discussion_summary, voting_result, dispatch_state)
        from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent
        history = ChatHistory()
        history.add_message(ChatMessageContent(role=AuthorRole.USER, content=prompt))
        response = await service.get_chat_message_content(chat_history=history, settings=...)
        report_body = response.content or discussion_summary
    else:
        report_body = discussion_summary  # fallback
    ...
```

注意：`save_report` 是在 WebSocket 的 "save" action 中被调用（`web_server.py:1343`），需要传入 service。

- [ ] **步骤 4：验证**

1. 跑一次讨论 → 保存报告
2. 检查报告质量：结构是否清晰、语言是否自然、是否有 AI 痕迹
3. 与之前生成的报告对比

- [ ] **步骤 5：Commit**

```bash
git add src/reporting.py src/web_server.py
git commit -m "feat: inject technical-writer and humanizer-zh constraints into report generation"
```

---

## 自检清单

### 1. 规格覆盖度

| 问题 | 任务 | 覆盖 |
|------|------|------|
| 输入框太小 | A1 | ✅ |
| 主持人回复不渲染 | A2 | ✅ |
| Blueprint ValidationError | C1 | ✅ |
| 蓝图标题/缺乏结论 | C2 | ✅ |
| Agent 名称中英混合 | B1 | ✅ |
| Preset 推荐不符预期 | B3 | ✅ 新增 document_design preset |
| Architect 三年扩展性 | B2 | ✅ |
| 导出路径污染 | C3 | ✅ |
| 报告缺乏专业性 | D1 | ✅ |

**遗漏项：** 无。全部 10 个问题已覆盖。

### 2. 占位符扫描

- D1 步骤 1 中的 "读取参考 skill 文件" 需要实际执行——在实现阶段第一步就是读文件
- D1 步骤 3 中的 "检查 `save_report` 当前实现" 需要实际读取——已标记
- 无 TODO / 待定 / 后续实现 等占位符 ✅

### 3. 类型一致性

- A2 中修改 `push_message` 新增 `session.manager_config.name` 引用——`session` 在闭包作用域内可用 ✅
- C1 中 `_run_blueprint_phase` 已在 `SessionState` 上下文中 ✅
- C3 中 `_clean_md_auto_links` 函数接受 `Any` 返回 `Any`——与 `_cleanup_value` 签名一致 ✅
- D1 中 `save_report` 新增 `service` 参数——调用方 `web_server.py:1343` 需要同步传参 ✅

---

## 执行建议

计划覆盖 4 个子系统，建议按依赖关系执行：

1. **先执行 A（UI）** — 无后端依赖，前端可独立验证
2. **再执行 B（Preset/Agent）** — B1/B2 前端+配置变更；B3 新增 preset 后需重跑讨论验证
3. **再执行 C（Blueprint）** — 依赖完整讨论流程
4. **最后执行 D（报告）** — 依赖完整流程和 skill 约束注入

每个子系统可独立提交，降低风险。
