# 外部 Skills 仓库对 Agent Preset 设计的可用性分析

> 分析日期：2026-05-04
>
> 分析对象：
> - https://github.com/mattpocock/skills（Matt Pocock 工程实践 skill 集）
> - https://github.com/ComposioHQ/awesome-codex-skills（Composio 社区 Codex skill 汇总）
>
> 目的：评估两个仓库中是否有可借鉴的 agent 角色定义和 skill 方法论，用于 agora 的 preset 角色池设计（见 `docs/plans/2026-05-04-agent-preset-design.md`）。

---

# 第一部分：mattpocock/skills

## 1. 仓库概览

Matt Pocock 的 skills 仓库是一个**工程实践类 skill 集合**，面向 AI 编程助手（Claude Code、Codex 等），按用途分桶组织：

| 分类 | 内容 | 数量 |
|------|------|------|
| engineering/ | 日常代码工作（diagnose, tdd, triage, to-prd, zoom-out 等） | 9 |
| productivity/ | 非代码工作流（grill-me, caveman, write-a-skill） | 3 |
| misc/ | 偶尔使用（git hooks, pre-commit, 迁移脚本等） | 4 |
| deprecated/ | 已废弃（ubiquitous-language, qa 等） | 4 |
| personal/ | 作者个人使用 | 2 |

**核心结论**：该仓库不是 agent 角色库，而是**软件开发流程的自动化工具**。但它有多个 skill 的内部方法论可以直接改造为 agent 的 system prompt。

## 2. 逐角色匹配分析

### 2.1 RequirementsAnalyst ← `grill-me`（匹配度：强）

`grill-me` 的访谈方法论与设计文档中 RequirementsAnalyst 的定义高度重合：

| grill-me 方法 | RequirementsAnalyst 设计要求 |
|---|---|
| "Interview relentlessly until shared understanding" | "追问具体的输入/输出/异常情况" |
| "Walk down each branch of the design tree, resolving dependencies one-by-one" | "用清单思维：列出所有需要覆盖的维度，逐项确认" |
| "Ask questions one at a time" | "当讨论发散时，拉回到用户的原始问题上" |
| "If a question can be answered by exploring the codebase, explore instead" | "区分用户说的和用户实际需要的" |

**借鉴建议**：把 grill-me 的"逐层决策树遍历"框架注入 RequirementsAnalyst 的 instructions。核心指令："对用户的每个需求描述，向下追问一层——直到找到可验证的验收标准为止。"

### 2.2 RootCauseAnalyst ← `diagnose`（匹配度：非常强）

`diagnose` 的 6 阶段诊断循环与根因分析的完整流程几乎一一对应：

| diagnose 阶段 | RootCauseAnalyst 设计等价物 |
|---|---|
| Phase 1 — Build a feedback loop | "时间线还原：事件的完整时间线是什么？关键节点在哪里？" |
| Phase 2 — Reproduce | "确认关键节点" |
| Phase 3 — Hypothesise（3-5 ranked, falsifiable） | "5-Why 分析：层层追问到系统性问题" |
| Phase 4 — Instrument（change one variable at a time） | "每个根因必须有对应的验证方式" |
| Phase 5 — Fix + regression test | "改进措施：如何验证改进有效？" |
| Phase 6 — Post-mortem: "what would have prevented this bug?" | "如果这个改进措施已经到位，这次事故能不能被避免？" |

关键方法论可直接翻译为 agent 指令：

- "Generate 3-5 ranked hypotheses before testing any of them" → 根因分析师的发言结构
- "Each hypothesis must be falsifiable: state the prediction it makes" → 避免模糊归因
- "If no correct test seam exists, that itself is the finding" → 复盘从"改代码"走向"改架构"的关键转折点

**借鉴建议**：把 diagnose 的 Phase 1-6 作为 RootCauseAnalyst 的发言框架，每轮讨论走一个阶段。

### 2.3 Evaluator ← `improve-codebase-architecture`（匹配度：强）

该 skill 定义了一套精准的结构化评估词汇，恰好解决了 Evaluator 的核心难题——"如何让评估不依赖主观感受？"

| IA 概念 | 对应 Evaluator 评估维度 | 定义 |
|---------|------------------------|------|
| **Depth** | 方案的投入产出比 | "a lot of behaviour behind a small interface" |
| **Leverage** | 方案对业务的增益 | "what callers get from depth" |
| **Locality** | 方案的可维护性 | "change, bugs, knowledge concentrated in one place" |
| **Seam** | 方案的边界清晰度 | "where an interface lives; a place behaviour can be altered without editing" |
| **Deletion test** | 方案必要性验证 | "imagine deleting it. If complexity vanishes, it was a pass-through" |

**借鉴建议**：每个方案都用 depth、leverage、locality、deletion test 四个维度打分。

### 2.4 DomainExpert ← `ubiquitous-language`（匹配度：中等）

虽已废弃，但其"术语消歧 → 标准化 → 场景举例"三段论对 DomainExpert 很有启发：识别领域术语歧义、引用行业标准术语、用具体场景而非抽象定义表达领域知识。

### 2.5 ProcessDesigner ← `triage`（匹配度：中等）

`triage` 定义了一个 issue 状态机，每个状态明确"谁负责、什么条件进入、什么条件离开"，与 ProcessDesigner 的"输入 → 判断 → 分支 → 汇合"思维一致。

### 2.6 scope 约束 ← `caveman`（匹配度：中等）

极简压缩风格（drop articles, filler, hedging）可以注入 scope 约束，强化"精准、无废话"的输出要求。注意取其精神（简洁）而非形式（电报体）。

## 3. 不相关的 skill

`tdd`、`to-issues`、`to-prd`、`setup-matt-pocock-skills`、`git-guardrails-claude-code`、`scaffold-exercises`、`setup-pre-commit`、`migrate-to-shoehorn`、`write-a-skill` 等与 agent 角色设计无直接关系。

## 4. Matt Pocock 小结

| 维度 | 评分 |
|------|------|
| 作为 agent 角色库 | ❌ 不适用 |
| 作为 agent 方法论来源 | ✅ 高价值 |
| 即插即用程度 | ⚠️ 需改造 |

---

# 第二部分：awesome-codex-skills

## 5. 仓库概览

Composio 维护的 Codex skill 汇总仓库，包含 50+ 个本地 skill 目录 + 1 个含 835 项技能的 `composio-skills/` 子目录 + 多个外部仓库引用。按用途分五大类：

| 分类 | 典型内容 | 数量级 |
|------|---------|--------|
| Development & Code Tools | 代码迁移、PR 审查、CI 修复、MCP 构建 | ~16 |
| Productivity & Collaboration | 会议纪要、工单分诊、文件整理、Connect 集成 | ~16 |
| Communication & Writing | 邮件润色、changelog、内容写作、简历定制 | ~7 |
| Data & Analysis | 竞品广告分析、Datadog 日志、股票研究 | ~9 |
| Meta & Utilities | 品牌色、skill 创建器、主题工厂、安装器 | ~10 |

**核心结论**：该仓库以工作流自动化 skill 为主，但有多个 skill 的内部分析框架——尤其是评分体系、模式识别、分类分诊方法论——可以直接注入 Evaluator 和 ProcessDesigner 的 system prompt。

## 6. 逐角色匹配分析

### 6.1 Evaluator ← `meeting-insights-analyzer` + `competitive-ads-extractor` + `lead-research-assistant`（匹配度：强）

三个 skill 从不同角度贡献了 **结构化评估方法论**：

| 来源 skill | 贡献给 Evaluator 的方法论 |
|---|---|
| `meeting-insights-analyzer` | "Pattern → Finding → Impact → Recommendation" 四段式输出结构，每个发现附带具体证据和量化数据 |
| `competitive-ads-extractor` | 多方案并行对比框架："what themes repeat? what's common? where do they differ?" ——这就是 Evaluator 做方案对比时的天然模板 |
| `lead-research-assistant` | 评分体系：fit score 1-10 + 具体评分依据，每个评分附带解释——这正是 Evaluator 需要的"决策矩阵 + 打分理由" |

**meeting-insights-analyzer 的输出模式尤其值得借鉴**：

```
### [Pattern Name]
**Finding**: [一句话总结]
**Frequency**: [X 次 / Y 项]
**Examples**:
  1. **What Happened**: [具体证据]
     **Why This Matters**: [影响解释]
     **Better Approach**: [改进建议]
```

这个结构可以直接转化为 Evaluator 的方案评估模板：

```
### [评估维度]
**评分**: [X/10]
**依据**: [引用讨论中的具体论据]
**风险**: [该维度下方案的最大弱点]
**替代考虑**: [是否有更好的选择]
```

**借鉴建议**：把 meeting-insights-analyzer 的"Finding → Impact → Recommendation" 和 lead-research-assistant 的"numeric score + evidence-based rationale" 合并为 Evaluator 的统一输出格式。

### 6.2 ProcessDesigner ← `create-plan` + `issue-triage` + `support-ticket-triage`（匹配度：强）

三个 skill 从不同角度贡献了**流程设计方法论**：

| 来源 skill | 贡献给 ProcessDesigner 的方法论 |
|---|---|
| `create-plan` | 结构化计划模板：Scope In/Out → Action Items（verb-first, atomic, ordered）→ Open Questions（max 3）。"Verb-first: Add…, Refactor…, Verify…" 可转化为流程步骤的命名规范 |
| `issue-triage` | 状态机驱动：Pull backlog → Cluster duplicates → Apply updates in one pass → Link duplicates → Post digest。这是完整的多阶段流程闭环 |
| `support-ticket-triage` | 分类分诊流程：Parse → Categorize（含 subcategory）→ Assign priority（P0-P3 with justification）→ Draft response → Quality checks。"If signal is weak, present 2-3 likely categories and what evidence would disambiguate"——处理不确定性的范式 |

**create-plan 的模板可直接借鉴**：

```markdown
## Scope
- In: [本流程覆盖的范围]
- Out: [明确不覆盖的边界]

## 流程步骤
[ ] Step 1 — 输入/触发条件 → 处理 → 输出/责任人
[ ] Step 2 — …
[ ] Step N — 闭环条件

## 异常路径
- [异常场景 1] → 处理方式 → 回退路径
- [异常场景 2] → …
```

**借鉴建议**：把 create-plan 的结构化模板和 support-ticket-triage 的分诊流程合并为 ProcessDesigner 的输出规范。

### 6.3 RootCauseAnalyst ← `sentry-triage`（匹配度：中等）

`sentry-triage` 虽然本质是 Composio CLI 操作指南，但其诊断流程对根因分析有参考价值：

- "Fetch issue → Grab latest event → Map each frame to local source → Check suspect commits → Propose a fix with a diff" ——这是结构化的"从现象到代码"追踪链路
- "Route to Linear/Slack"——复盘后必须关联到可执行工单，与 RootCauseAnalyst 的"改进措施必须可验证、有 owner"一致

**借鉴建议**：把 sentry-triage 的"frame mapping"概念转化为 RootCauseAnalyst 的"事件→影响链路映射"步骤。

### 6.4 Synthesizer ← `meeting-notes-and-actions`（匹配度：强）

`meeting-notes-and-actions` 的输出结构与你设计文档中 Synthesizer 的要求几乎完全匹配：

| meeting-notes-and-actions 输出 | Synthesizer 设计要求 |
|---|---|
| Header（meeting title, date, attendees） | "话题 [一句话描述]" |
| Summary | "讨论结论" |
| Decisions | "达成共识" |
| Open Questions / Risks | "仍有分歧" + "风险清单" |
| Action Items（checkboxes with owner + due） | "行动项 [含负责角色和验收标准]" |
| Quality checks: "no hallucinated facts; flag ambiguities" | "总结必须体现讨论的动态过程，不能静态罗列" |

**借鉴建议**：直接把 meeting-notes-and-actions 的输出结构作为 Synthesizer 的模板基线，补上 agora 特有的"核心分歧与演进"和"主持人倾向"字段即可。

### 6.5 DomainExpert ← 无直接匹配

awesome-codex-skills 中没有专门的领域知识注入或术语标准化 skill。`internal-comms` 侧重企业内部沟通而非领域知识，`lead-research-assistant` 侧重销售线索而非技术领域 expertise。DomainExpert 的方法论来源仍然以 mattpocock/skills 的 `ubiquitous-language` 为最佳参考。

## 7. 不相关的 skill

以下分类与 agent 角色设计无直接关系：

- **代码自动化**：`codebase-migrate`、`deploy-pipeline`、`gh-address-comments`、`gh-fix-ci`、`pr-review-ci-fix`、`webapp-testing`
- **媒体/设计**：`brand-guidelines`、`canvas-design`、`image-enhancer`、`slack-gif-creator`、`theme-factory`、`video-downloader`、`paperjsx`
- **内容生成**：`changelog-generator`、`email-draft-polish`、`tailored-resume-generator`、`content-research-writer`
- **文件/数据操作**：`file-organizer`、`invoice-organizer`、`spreadsheet-formula-helper`、`raffle-winner-picker`
- **元工具**：`template-skill`、`skill-installer`、`skill-creator`、`skill-share`、`agent-deep-links`、`connect`、`connect-apps`
- **Notion 系列**（4 个）——数据搬运而非角色方法论
- **Linear/Jira 操作**——同上

---

# 第三部分：agent-skills（Addy Osmani）

## 8. 仓库概览

Addy Osmani 的 agent-skills 是三个仓库中**最贴近 agent 角色设计需求**的一个。它覆盖完整的软件开发生命周期（Define → Plan → Build → Verify → Review → Ship），含 20 个工程 skill + 3 个预定义 agent 角色 + 4 个参考检查清单。

关键区别：这个仓库**有真正的 agent 角色定义文件**（`agents/` 目录），不仅仅是工作流 skill。

**核心结论**：这是对 agora preset 设计**借鉴价值最高**的仓库——既有可直接参考的 agent 角色结构，又有可改造为角色指令的 skill 方法论，还有独树一帜的"反合理化表"（anti-rationalization）设计模式。

## 9. Agent 角色文件分析（可直接借鉴）

这是三个仓库中唯一包含预定义 agent 角色的。三个角色均为"审查型"（reviewer），而非"讨论参与者"型，但其角色定义结构——领域视角、评估维度、输出格式、行为规则——可以直接用作 agora 角色指令的模板。

### 9.1 code-reviewer → Evaluator / Challenger（匹配度：强）

五轴评审框架（correctness, readability, architecture, security, performance）与 Evaluator 的多维度评估思路完全一致：

| code-reviewer 五轴 | 可转化为 Evaluator 评估维度 | 可转化为 Challenger 质疑角度 |
|---|---|---|
| Correctness | 方案逻辑的正确性 | "如果这个逻辑有漏洞，后果是什么？" |
| Readability | 方案的可理解性 / 沟通成本 | — |
| Architecture | 系统影响、模块边界 | "这个方案破坏了哪些现有边界？" |
| Security | 风险评估 | "这个方案引入了什么新风险？" |
| Performance | 效率评估 | — |

此外，其三档严重性分类（Critical / Important / Suggestion）和 "Every finding must include a specific fix recommendation" 原则，可以直接转化为 Evaluator 的输出格式。

### 9.2 security-auditor → DomainExpert（安全领域）（匹配度：强）

这个角色是 DomainExpert 的领域特化版本（安全领域）。其结构可以直接作为 DomainExpert 的模板：

- **审查范围**（Review Scope）→ DomainExpert 的"领域检查清单"（Input Handling / Auth / Data / Infrastructure / Third-Party）
- **严重性分类**（Critical / High / Medium / Low / Info）→ 领域风险评级体系
- **输出格式**："Description → Impact → Proof of concept → Recommendation" 四段式
- **每项发现附带可操作建议** → 对应 DomainExpert 的"给出领域特定的检查清单"

**借鉴建议**：把 security-auditor 的角色结构作为 DomainExpert 的模板骨架，替换安全领域内容为通用领域知识注入模式。

### 9.3 test-engineer → Evaluator（质量视角）（匹配度：中等）

"Prove-It 模式"（写一个证明 bug 存在的测试 → 确认失败 → 报告测试就绪）对应 Evaluator 的"每个评分必须有具体依据"。场景覆盖表（Happy path / Empty input / Boundary values / Error paths / Concurrency）可作为 Evaluator 评估方案时的"覆盖度检查清单"。

## 10. 核心 Skill 方法论分析

### 10.1 RequirementsAnalyst ← `idea-refine` + `spec-driven-development`（匹配度：非常强）

这两个 skill 结合起来，几乎完整覆盖了 RequirementsAnalyst 的设计需求：

**`idea-refine` 的贡献——需求发散与收敛**：

| idea-refine 方法 | RequirementsAnalyst 对应 |
|---|---|
| Phase 1 (Divergent): "How Might We" problem statement | "用户真正要解决的问题是什么？" |
| "Generate 5-8 idea variations" via Inversion / Constraint removal / Audience shift / Simplification / 10x version | "完整性检查：还缺哪些必要信息？" |
| Phase 2 (Convergent): Stress-test against User value / Feasibility / Differentiation | "优先级判断：哪些是 Must-have，哪些是 Nice-to-have？" |
| "Surface hidden assumptions: what you're betting is true" | 需求分析师的场景驱动方法 |
| "Not Doing list" | "不做的事" 边界定义 |
| "Be honest, not supportive. Push back on weak ideas" | "当有人跳到实现方案时，追问'这解决的是用户的哪个需求？'" |

**`spec-driven-development` 的贡献——假设外化与边界定义**：

- "Surface assumptions immediately. Before writing any spec content, list what you're assuming" → RequirementsAnalyst 的"区分用户说的和用户实际需要的"
- "Six core spec areas"（Objective, Commands, Structure, Style, Testing, Boundaries）→ 需求分析师的"每个需求点都对应一个具体的使用场景"
- "Three-tier boundary system"（Always do / Ask first / Never do）→ 对应你的 scope 约束设计

**借鉴建议**：这两个 skill 的方法论合并后，几乎可以直接作为 RequirementsAnalyst 的完整 system prompt。idea-refine 负责"需求发散→收敛"，spec-driven-development 负责"假设外化→边界定义"。

### 10.2 RootCauseAnalyst ← `debugging-and-error-recovery`（匹配度：非常强）

与 mattpocock 的 `diagnose` 形成互补。`diagnose` 强在"假设驱动的诊断哲学"（hypotheses, falsifiability），而这个 skill 强在"操作流程的结构化"：

- **Stop-the-Line Rule**：STOP → PRESERVE → DIAGNOSE → FIX → GUARD → RESUME。这是根因分析的标准操作纪律
- **Triage Checklist**：Reproduce → Localize → Reduce → Fix → Guard，每步有明确的决策分支
- **不可复现 bug 的处理决策树**：Timing-dependent? / Environment-dependent? / State-dependent? / Truly random? ——每类有对应的调查策略
- **"Errors compound. A bug in Step 3 that goes unfixed makes Steps 4-10 wrong"** → RootCauseAnalyst 的"区分表面原因和根本原因"

**借鉴建议**：把 `diagnose` 的 Phase 1-6（诊断哲学）和 `debugging-and-error-recovery` 的 Stop-the-Line + Triage Checklist（操作流程）合并为 RootCauseAnalyst 的完整思维框架。

### 10.3 ProcessDesigner ← `planning-and-task-breakdown`（匹配度：强）

该 skill 的垂直切片（vertical slicing）方法论与 ProcessDesigner 的流程设计思路高度吻合：

- **Dependency graph mapping** → ProcessDesigner 的"这个流程有几个关键阶段？"
- **Vertical slicing**（一条用户路径的完整实现，而非按技术层拆分）→ 流程设计的"输入→处理→输出→负责人"单一路径闭环
- **Task granularity**："small enough to implement, test, and verify in a single focused session" → 流程步骤的"可执行、可验证"要求
- **Read-only planning mode**：先分析再设计 → ProcessDesigner 的"当讨论过于抽象时，要求具体到'谁在什么时候做什么'"

**借鉴建议**：把 planning-and-task-breakdown 的垂直切片方法作为 ProcessDesigner 的流程分解原则。

### 10.4 独有亮点："反合理化表"（Anti-Rationalization）

agent-skills 的一个独特设计模式是每个 skill 都包含**反合理化表**——列出 agent 常用的跳过步骤的借口及其反驳：

```
"What I'll do instead"          | "Why that's not the same"
"I'll add tests later"          | Tests written later have lower coverage and miss edge cases
"It's a small change"           | Small changes cause the most surprising regressions
"I already tested it manually"  | Manual testing doesn't protect against future changes
```

这个模式可以直接用于 agora 的 scope 约束——让讨论参与者知道"哪些借口是不可接受的"。

---

# 第四部分：三仓库综合评估

## 11. 三仓库互补全景

| 角色 | 最佳方法论来源 | 贡献内容 |
|------|-------------|---------|
| **RequirementsAnalyst** | agent-skills `idea-refine` + `spec-driven-development` | 发散收敛思维 + 假设外化 + Not Doing 列表 + 三档边界系统 |
| **DomainExpert** | agent-skills `security-auditor`（角色结构） + mattpocock `ubiquitous-language`（方法论） | 角色定义模板 + 术语消歧标准化 |
| **Evaluator** | agent-skills `code-reviewer`（五轴框架） + mattpocock `improve-codebase-architecture`（评估词汇） + codex `meeting-insights-analyzer`（模式识别） | 评审维度 + 评估词汇 + 评分方法论 |
| **ProcessDesigner** | agent-skills `planning-and-task-breakdown`（垂直切片） + mattpocock `triage`（状态机） + codex `create-plan`（计划模板） | 流程分解方法 + 状态转移模型 + 结构化计划 |
| **RootCauseAnalyst** | mattpocock `diagnose`（诊断哲学） + agent-skills `debugging-and-error-recovery`（操作流程） | 假设驱动的 6 阶段循环 + Stop-the-Line 操作纪律 |
| **Synthesizer** | codex `meeting-notes-and-actions`（输出模板） | 结构化总结格式（几乎即插即用） |
| **scope 约束** | agent-skills "反合理化表" + mattpocock `caveman` | 禁止借口 + 极简表达 |

## 12. 分仓库价值评级

| 仓库 | Agent 角色库 | 方法论来源 | 即插即用 | 独有亮点 | 总体评级 |
|------|:--:|:--:|:--:|------|:--:|
| **mattpocock/skills** | ❌ | ⭐⭐⭐⭐ | ⚠️ | caveman 极简模式 | ⭐⭐⭐ |
| **awesome-codex-skills** | ❌ | ⭐⭐⭐ | ⚠️ | 评分体系 + 分诊流程 | ⭐⭐ |
| **agent-skills** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ | 真实 agent 角色 + 反合理化表 | ⭐⭐⭐⭐⭐ |

## 13. 最终结论

三个仓库都对 agora 的 preset 设计有贡献，但贡献类型不同：

- **agent-skills**（Addy Osmani）是**最高价值来源**。它不仅提供了可参考的 agent 角色结构（code-reviewer、security-auditor、test-engineer），还有可以直接改造为角色 system prompt 的 skill 方法论（idea-refine、spec-driven-development、debugging-and-error-recovery、planning-and-task-breakdown），以及独树一帜的"反合理化表"设计模式。
- **mattpocock/skills** 的 `diagnose` 和 `grill-me` 分别对 RootCauseAnalyst 和 RequirementsAnalyst 有无法替代的贡献。
- **awesome-codex-skills** 的 `meeting-notes-and-actions` 为 Synthesizer 提供了即插即用的输出模板。

建议落地优先级：

1. **RootCauseAnalyst** ← 合并 `diagnose`（哲学）+ `debugging-and-error-recovery`（流程）
2. **RequirementsAnalyst** ← 合并 `idea-refine`（发散收敛）+ `spec-driven-development`（假设外化）+ `grill-me`（决策树遍历）
3. **Synthesizer** ← `meeting-notes-and-actions` 输出模板
4. **Evaluator** ← `code-reviewer` 五轴框架 + `improve-codebase-architecture` 评估词汇
5. **ProcessDesigner** ← `planning-and-task-breakdown` 垂直切片 + `triage` 状态机
6. **DomainExpert** ← `security-auditor` 角色结构 + `ubiquitous-language` 方法论
7. **scope 约束** ← 反合理化表 + `caveman` 极简风格

## 8. 两仓库互补性对比

两个仓库恰好形成互补关系：

| 角色 | 主要方法论来源 | 贡献内容 |
|------|-------------|---------|
| **RequirementsAnalyst** | mattpocock `grill-me` | 决策树遍历访谈模式 |
| **DomainExpert** | mattpocock `ubiquitous-language` | 术语消歧 → 标准化 → 场景举例 |
| **Evaluator** | mattpocock `improve-codebase-architecture` + codex `meeting-insights-analyzer` + `lead-research-assistant` | 评估词汇体系 + 模式识别四段式 + 评分方法论 |
| **ProcessDesigner** | mattpocock `triage` + codex `create-plan` + `support-ticket-triage` | 状态机模型 + 结构化计划模板 + 分诊流程 |
| **RootCauseAnalyst** | mattpocock `diagnose` | 6 阶段诊断循环（无替代方案，这是唯一最佳来源） |
| **Synthesizer** | codex `meeting-notes-and-actions` | 输出结构模板（几乎即插即用） |
| **scope 约束** | mattpocock `caveman` | 极简表达风格 |

## 9. 总体结论

两个仓库都不包含可直接引用的 agent 角色定义——它们本质上是**工作流自动化工具**和**工程方法论 skill**，不是"人设指令集"。但以下几个 skill 的内部方法论对 agora 的 preset 角色设计具有高价值借鉴意义：

**第一梯队（最高价值，建议优先落地）**：

- `diagnose` → RootCauseAnalyst：6 阶段循环几乎可以即插即用
- `meeting-notes-and-actions` → Synthesizer：输出结构与设计要求完全匹配
- `grill-me` → RequirementsAnalyst：决策树遍历模式精准对应

**第二梯队（有价值，建议后续跟进）**：

- `improve-codebase-architecture` + `meeting-insights-analyzer` + `lead-research-assistant` → Evaluator：综合贡献评估词汇、模式识别、评分体系
- `create-plan` + `triage` + `support-ticket-triage` → ProcessDesigner：综合贡献流程模板、状态机、分诊逻辑

**第三梯队（可参考但不急）**：

- `ubiquitous-language` → DomainExpert：术语消歧方法论
- `caveman` → scope 约束：简洁性要求