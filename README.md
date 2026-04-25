# Agent Discussion

> 基于 Microsoft Semantic Kernel 的多 Agent 群组讨论、投票与报告生成工具，提供 **CLI** 与 **Web UI** 两种交互方式。

让多个不同模型、不同人设的 LLM agent 围绕一个议题进行有主持人控场的真实讨论，独立投票，并自动产出可读的会议纪要。

## Features

- **多角色协作**：主持人 (Host) + 架构师 / 务实派 / 反方等专家 agent，每个 agent 可挂不同模型
- **LLM 驱动主持**：基于 Semantic Kernel `GroupChatOrchestration`，由主持人 LLM 决定谁发言、何时收敛
- **议题精炼（可选）**：讨论开始前由主持人通过多轮 Q&A 帮用户把模糊议题精炼为可讨论的精准问题
- **独立投票**：专家 agent 并行表态（赞成 / 反对 / 中立 + 置信度 + 理由），本地聚合
- **追问 (Follow-up)**：投票后用户可基于完整对话上下文追加问题
- **报告归档**：经用户确认后保存为 markdown，沉淀讨论资产
- **SSE 代理适配**：内置 `openai_sse_proxy`，可对接只支持 SSE 流式的本地代理（如 `http://localhost:3030/v1`）
- **Web UI**：实时 timeline 展示发言、流式打字、投票卡、报告管理

## Installation

### Prerequisites

- Python ≥ 3.10
- Node.js ≥ 18（仅 Web UI 需要）
- 一个 OpenAI 兼容的 LLM 端点（OpenAI 官方 / Azure OpenAI / 本地代理 / 第三方兼容服务）

### 安装步骤

```bash
cd /Users/lvzhibo/Agent/agent-discussion

# 安装后端依赖和开发测试依赖
pip install -e ".[dev]"

# 安装前端依赖
cd frontend && npm install
```

如需继续使用本机 Semantic Kernel 源码调试，可额外执行：

```bash
pip install -e /Users/lvzhibo/Downloads/semantic-kernel-main/python
```

> 安装完成后，`agent-discussion`（CLI）和 `agent-discussion-web`（Web 后端）两个命令会全局可用。

默认配置使用环境变量读取 key。可复制 `.env.example` 为 `.env`，填入本地代理和兼容模型服务的 key。

## Quick Start

### 方式 A：Web UI（推荐）

```bash
cd /Users/lvzhibo/Agent/agent-discussion
./start.sh
```

启动后访问：
- 前端：http://localhost:5173
- 后端：http://localhost:8001

首次运行会自动 `npm install` 前端依赖。`Ctrl+C` 同时停止两个进程。

### 方式 B：CLI

```bash
# 使用内置默认配置
agent-discussion -t "我们应该用 GraphQL 还是 REST？"

# 指定自定义配置
agent-discussion -c /path/to/my_agents.yaml -t "评估架构 Y"

# 详细日志
agent-discussion -t "测试" -v
```

## Usage

### 一次完整的会话流程

```
用户输入议题
    ↓
[brainstorming] 主持人多轮 Q&A 精炼议题（可跳过）
    ↓
[discussion]    专家 agents 由主持人调度轮流发言
    ↓
[summary]       主持人汇总讨论结论
    ↓
[voting]        每个 agent 独立投票 + 理由
    ↓
[follow-up]     用户追问（可选，支持多轮）
    ↓
[saved]         用户确认后保存为 markdown 报告
```

### 配置文件示例（`src/config/agents.yaml`）

```yaml
manager_service_index: 0  # 用第几个 agent 的 service 作为主持人 LLM

agents:
  - name: Host
    description: "主持人，控场 + 选人 + 收敛"
    instructions: "你是讨论主持人……"
    service_type: openai_sse_proxy
    model: gpt-4o
    api_key: "${YOUR_API_KEY}"
    base_url: "http://localhost:3030/v1"

  - name: Architect
    description: "架构师，关注扩展性与抽象"
    instructions: "你倾向于关注长期影响……"
    service_type: openai_compatible
    model: glm-4.6
    api_key: "${YOUR_API_KEY}"
    base_url: "https://your-endpoint.com/v1"

  - name: Synthesizer
    description: "总结者，最后输出行动项"
    final_only: true   # 仅在终结轮发言
    instructions: "请输出可执行的下一步……"
    service_type: openai_sse_proxy
    model: gpt-4o
    api_key: "${YOUR_API_KEY}"
    base_url: "http://localhost:3030/v1"

# 可选：覆盖默认配置
discussion:
  enabled: true
  max_rounds: 10

voting:
  enabled: true

brainstorm:
  enabled: true
  max_rounds: 5
  answer_timeout_seconds: 300
```

环境变量插值用 `${VAR_NAME}` 语法，自动从 `os.environ` 读取。

## Architecture

```
┌──────────────────────┐
│   Web UI (React)     │  port 5173
│   - Timeline         │
│   - VotingCard       │
│   - AgentStatusPanel │
└──────────┬───────────┘
           │ WebSocket /ws/{session_id}
           ▼
┌──────────────────────┐
│  FastAPI (web_server)│  port 8001
│  - SessionManager    │
│  - 事件推送          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Pipeline                                │
│  brainstorm → discussion → voting → ... │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Semantic Kernel                         │
│  GroupChatOrchestration                  │
│  + LLMGroupChatManager (自定义)          │
│    - select_next_agent (LLM)             │
│    - should_terminate (LLM + min_rounds) │
│    - filter_results (LLM 总结)           │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Service Adapter                         │
│  - OpenAIChatCompletion (官方/兼容)      │
│  - SSEProxyAsyncOpenAI (本地 SSE 代理)   │
└──────────────────────────────────────────┘
```

### 关键模块

| 文件 | 职责 |
|------|------|
| `src/cli.py` | CLI 入口，串联 `loader → pipeline` |
| `src/web_server.py` | FastAPI + WebSocket，会话生命周期、事件推送、报告/会话 API |
| `src/pipeline.py` | CLI 端的 discussion → voting → confirm → save 串联 |
| `src/discussion.py` | `LLMGroupChatManager`：LLM 驱动的选人/终止/总结，含 `min_rounds` 守卫 |
| `src/brainstorm.py` | `BrainstormSession`：主持人多轮 Q&A 精炼议题（含降级策略） |
| `src/voting.py` | 并行投票 + 本地聚合（赞成/反对/中立 + 置信度） |
| `src/loader.py` | YAML 配置加载、agent 实例化、kernel 注册 |
| `src/openai_sse_proxy.py` | 适配 SSE-only 本地代理，支持 SK 的 streaming 路径 |
| `src/reporting.py` | 把对话和投票渲染成 markdown |
| `src/models.py` | Pydantic 配置模型 |
| `src/web_entry.py` | 可安装的 Web 后端入口 |

## Configuration

### Pipeline 开关

```yaml
discussion:
  enabled: true       # 关闭则跳过群组讨论
  max_rounds: 10      # 硬上限

voting:
  enabled: true       # 关闭则跳过投票

brainstorm:
  enabled: true       # 关闭则直接进入 discussion
  max_rounds: 5
```

### 结构化输出回退

部分 LLM 端点不支持 `response_format=json_schema`，可在配置顶层设置：

```yaml
supports_structured_output: false
```

`LLMGroupChatManager` 会回退到 prompt + regex 解析模式。

### 内置示例配置

| 文件 | 用途 |
|------|------|
| `src/config/agents.yaml` | 默认完整配置 |
| `src/config/discussion_only.yaml` | 仅讨论，不投票 |
| `src/config/voting_only.yaml` | 仅投票，不讨论 |

## Troubleshooting

### Error: `openai_sse_proxy currently supports non-streaming callers only`

**原因**：旧版 `openai_sse_proxy.py` 未实现 streaming 路径，而 SK 的 `GroupChatOrchestration` 强制 `stream=True`。

**解决**：当前版本已修复（`SSEProxyAsyncOpenAI` 通过 `_PseudoAsyncStream` 注册为 `openai.AsyncStream` 的虚拟子类）。如果仍报错，确认 `src/openai_sse_proxy.py` 中存在 `_OpenAIAsyncStream.register(_PseudoAsyncStream)` 调用。

### 讨论没人发言就出结论

**原因**：LLM 在 round 1 判定"应该结束"，导致 agents 一句话都没说就进入总结。

**解决**：当前版本已加 `min_rounds` 守卫，默认 `min_rounds = max(1, len(agents))`，强制每个 agent 至少有发言机会。位置：`src/discussion.py` 的 `LLMGroupChatManager.should_terminate()`。

### 用户消息显示为 "Unknown"

**原因**：旧版 `web_server.py` 把所有无 name 的消息一律 fallback 成 "Unknown"。

**解决**：当前版本按 role 区分——`role=user` → "用户"，`role=assistant` → "匿名"。位置：`src/web_server.py::push_message`。

### 前端 5173 端口被占用

```bash
lsof -i :5173 | cat
# 或：cd frontend && npx vite --port 5174 --host
```

## Development

更多上下文见根目录的 `CLAUDE.md`（项目记忆）和 `KNOWN_ISSUES.md`（遗留问题清单）。

### 添加新 agent

在 `src/config/agents.yaml` 的 `agents` 列表追加一个条目即可，无需改代码。`description` 字段是必填的——`GroupChatOrchestration` 会用它生成给主持人 LLM 的"参与者介绍"。

## License

本项目从 Semantic Kernel 主仓库拆出后独立管理，许可证沿用上游 MIT License。
