import asyncio
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncStream
from openai.types.completion_usage import CompletionUsage

sys.path.append(str(Path(__file__).resolve().parents[1]))

from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

from src.discussion import (
    LLMGroupChatManager,
    _run_managed_group_chat,
    _strip_hidden_reasoning,
    build_discussion_transcript,
    run_discussion,
)
from src.loader import create_service
from src.brainstorm import BrainstormSession
from src.models import AgentConfig, AppConfig, BrainstormConfig, DiscussionConfig, ServiceType, VotingConfig
from src.openai_sse_proxy import SSEProxyAsyncOpenAI, _build_chat_completion_from_sse
from src.pipeline import run_pipeline
from src.reporting import get_default_report_dir, save_report
from src.voting import _parse_vote, run_voting


class FakeAgent:
    def __init__(self, name: str, response_text: str = "", delay: float = 0.0):
        self.name = name
        self.response_text = response_text
        self.delay = delay
        self.captured_messages = None

    async def get_response(self, messages=None, **kwargs):
        self.captured_messages = messages
        if self.delay:
            await asyncio.sleep(self.delay)
        return SimpleNamespace(
            message=ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                name=self.name,
                content=self.response_text,
            )
        )


def _build_config() -> AppConfig:
    return AppConfig(
        agents=[
            AgentConfig(
                name="Debater",
                description="discussion",
                instructions="discussion",
                service_type=ServiceType.OPENAI,
                model="test-model",
                api_key="test-key",
            ),
            AgentConfig(
                name="Synthesizer",
                description="summary",
                instructions="summary",
                service_type=ServiceType.OPENAI,
                model="test-model",
                api_key="test-key",
                final_only=True,
            ),
        ],
        discussion=DiscussionConfig(enabled=True, max_rounds=2),
        voting=VotingConfig(enabled=False),
    )


def test_build_discussion_transcript_includes_full_visible_history():
    history = ChatHistory()
    history.add_message(ChatMessageContent(role=AuthorRole.USER, content="主题"))
    history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Architect", content="先做 MVP"))
    history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Pragmatist", content="两周能上线"))
    history.add_message(ChatMessageContent(role=AuthorRole.SYSTEM, content="ignore"))

    transcript = build_discussion_transcript(history)

    assert "[user] 主题" in transcript
    assert "[Architect] 先做 MVP" in transcript
    assert "[Pragmatist] 两周能上线" in transcript
    assert "ignore" not in transcript


def test_strip_hidden_reasoning_removes_unclosed_think_blocks():
    assert _strip_hidden_reasoning("<think>internal scratchpad") == ""
    assert _strip_hidden_reasoning("<think>internal</think>最终结论") == "最终结论"


@pytest.mark.asyncio
async def test_run_pipeline_passes_full_transcript_to_final_synthesizer(monkeypatch, capsys):
    config = _build_config()

    history = ChatHistory()
    history.add_message(ChatMessageContent(role=AuthorRole.USER, content="是否上线"))
    history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Architect", content="建议先灰度"))
    history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Pragmatist", content="可以本周发布"))

    discussion_agent = FakeAgent(name="Debater")
    synthesizer = FakeAgent(name="Synthesizer", response_text="总结完成")

    async def fake_run_discussion(*args, **kwargs):
        return "", history

    monkeypatch.setattr("src.pipeline.run_discussion", fake_run_discussion)
    monkeypatch.setattr("src.pipeline.run_followup", lambda *args, **kwargs: history)
    monkeypatch.setattr("src.pipeline.create_service", lambda *_args, **_kwargs: object())

    created = {
        "Debater": discussion_agent,
        "Synthesizer": synthesizer,
    }

    def fake_create_agent(config):
        return created[config.name]

    monkeypatch.setattr("src.pipeline.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "q")

    await run_pipeline(config, "是否上线")

    prompt = synthesizer.captured_messages[0].content
    assert "以下是完整讨论记录" in prompt
    assert "建议先灰度" in prompt
    assert "可以本周发布" in prompt
    assert "未提供讨论内容" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_run_voting_does_not_block_on_slow_agent():
    fast_agent = FakeAgent(
        name="Fast",
        response_text='{"agent_name":"Fast","stance":"赞成","reason":"ok","confidence":0.9}',
    )
    slow_agent = FakeAgent(name="Slow", response_text="late", delay=0.2)

    result = await run_voting(
        agents=[fast_agent, slow_agent],
        topic="test",
        discussion_context="ctx",
        voting_prompt="vote",
        per_agent_timeout=0.05,
    )

    assert len(result.votes) == 2
    assert result.votes[0].agent_name == "Fast"
    assert result.votes[0].stance == "赞成"
    assert result.votes[1].agent_name == "Slow"
    assert result.votes[1].stance == "中立"
    assert "超时" in result.votes[1].reason
    assert "多数赞成" in result.conclusion


def test_default_report_dir_uses_singular_report_directory():
    assert get_default_report_dir().name == "report"


def test_report_includes_dispatch_execution_metadata(tmp_path):
    report_path = save_report(
        topic="原议题",
        discussion_summary="最终方案",
        discussion_transcript="讨论记录",
        voting_result=None,
        dispatch_state={
            "original_topic": "原议题",
            "refined_topic": "精炼议题",
            "complexity": {"level": "medium"},
            "execution_mode": "focused",
            "selected_agents": ["Architect"],
            "expected_final_output": "安全工单字段清单",
        },
        output_dir=tmp_path,
    )

    content = report_path.read_text(encoding="utf-8")
    assert "## 执行计划" in content
    assert "执行模式：focused" in content
    assert "派发 agent：Architect" in content
    assert "最终产出：安全工单字段清单" in content


def test_create_service_supports_openai_sse_proxy():
    config = AgentConfig(
        name="Proxy",
        description="proxy",
        instructions="proxy",
        service_type=ServiceType.OPENAI_SSE_PROXY,
        model="gpt-5.4",
        api_key="xx",
        base_url="http://localhost:3030/v1",
    )

    service = create_service(config)

    assert isinstance(service, OpenAIChatCompletion)
    assert isinstance(service.client, SSEProxyAsyncOpenAI)
    assert service.service_url() == "http://localhost:3030/v1/"


def test_run_web_log_config_includes_src_logger():
    import run_web

    log_config = run_web._build_log_config()

    assert log_config["disable_existing_loggers"] is False
    assert log_config["loggers"]["src"]["level"] == "INFO"
    assert log_config["loggers"]["src"]["handlers"] == ["default"]


def test_parse_vote_strips_think_blocks_from_reason():
    vote = _parse_vote(ChatMessageContent(
        role=AuthorRole.ASSISTANT,
        name="Architect",
        content=(
            '{"agent_name":"Architect","stance":"赞成",'
            '"reason":"<think>internal scratchpad</think>建议先小范围验证",'
            '"confidence":0.8}'
        ),
    ))

    assert "think" not in vote.reason
    assert "internal scratchpad" not in vote.reason
    assert vote.reason == "建议先小范围验证"


def test_brainstorm_defaults_use_general_interview_gates():
    config = BrainstormConfig()

    assert config.max_rounds == 10
    prompt = config.system_prompt
    assert "Ask ONE question at a time" in prompt
    assert "Do not overfit to one domain" in prompt
    assert "Current state" in prompt
    assert "Evidence gap" in prompt
    assert "Non-goals" in prompt
    assert "Decision boundaries" in prompt
    assert "Success criteria" in prompt
    assert "Finalize only when" in prompt
    assert "PR" not in prompt


def test_dispatch_state_filters_to_real_discussion_agents():
    from src import web_server

    config = AppConfig(
        agents=[
            AgentConfig(
                name="Host",
                description="主持人",
                instructions="控场",
                service_type=ServiceType.OPENAI,
                model="host-model",
                api_key="host-key",
            ),
            AgentConfig(
                name="Architect",
                description="架构师",
                instructions="架构",
                service_type=ServiceType.OPENAI,
                model="architect-model",
                api_key="architect-key",
            ),
            AgentConfig(
                name="Pragmatist",
                description="务实派",
                instructions="落地",
                service_type=ServiceType.OPENAI,
                model="pragmatist-model",
                api_key="pragmatist-key",
            ),
            AgentConfig(
                name="Synthesizer",
                description="总结者",
                instructions="总结",
                service_type=ServiceType.OPENAI,
                model="sum-model",
                api_key="sum-key",
                final_only=True,
            ),
        ],
        manager_service_index=0,
    )

    state = web_server._build_dispatch_state(
        original_topic="原议题",
        refined_topic="精炼议题",
        context_summary="摘要",
        raw_complexity={"level": "medium", "rationale": "需要拆分"},
        raw_dispatch_plan={
            "execution_mode": "focused",
            "tasks": [
                {"agent_name": "Ghost", "sub_topic": "不存在"},
                {"agent_name": "Host", "sub_topic": "主持人不能执行"},
                {"agent_name": "Synthesizer", "sub_topic": "final_only 不能讨论"},
                {"agent_name": "Architect", "sub_topic": "评估结构", "expected_output": "架构建议"},
                {"agent_name": "Architect", "sub_topic": "重复项"},
            ],
            "expected_final_output": "输出工单字段清单",
            "rationale": "只需要架构视角",
        },
        config=config,
    )

    assert state["execution_mode"] == "focused"
    assert state["selected_agents"] == ["Architect"]
    assert state["dispatch_plan"]["tasks"] == [
        {
            "agent_name": "Architect",
            "sub_topic": "评估结构",
            "expected_output": "架构建议",
        }
    ]
    assert state["expected_final_output"] == "输出工单字段清单"


def test_invalid_low_complexity_dispatch_falls_back_to_direct():
    from src import web_server

    config = AppConfig(
        agents=[
            AgentConfig(
                name="Host",
                description="主持人",
                instructions="控场",
                service_type=ServiceType.OPENAI,
                model="host-model",
                api_key="host-key",
            ),
            AgentConfig(
                name="Architect",
                description="架构师",
                instructions="架构",
                service_type=ServiceType.OPENAI,
                model="architect-model",
                api_key="architect-key",
            ),
        ],
        manager_service_index=0,
    )

    state = web_server._build_dispatch_state(
        original_topic="原议题",
        refined_topic="精炼议题",
        context_summary="",
        raw_complexity={"level": "low", "rationale": "简单"},
        raw_dispatch_plan={"tasks": [{"agent_name": "Ghost", "sub_topic": "不存在"}]},
        config=config,
    )

    assert state["execution_mode"] == "direct"
    assert state["selected_agents"] == []
    assert state["dispatch_plan"]["tasks"] == []


@pytest.mark.asyncio
async def test_send_json_serializes_openai_usage_metadata():
    from src.web_server import _send_json

    class FakeWebSocket:
        def __init__(self):
            self.payload = ""

        async def send_text(self, data: str):
            self.payload = data

    ws = FakeWebSocket()

    await _send_json(
        ws,
        {
            "type": "message",
            "meta": {
                "usage": CompletionUsage(
                    prompt_tokens=1,
                    completion_tokens=2,
                    total_tokens=3,
                )
            },
        },
    )

    event = json.loads(ws.payload)
    assert event["meta"]["usage"]["total_tokens"] == 3


@pytest.mark.asyncio
async def test_run_voting_prompt_forbids_think_blocks():
    agent = FakeAgent(
        name="Architect",
        response_text='{"agent_name":"Architect","stance":"赞成","reason":"ok","confidence":0.8}',
    )

    await run_voting(
        agents=[agent],
        topic="topic",
        discussion_context="context",
        voting_prompt="vote",
    )

    prompt = agent.captured_messages[0].content
    assert "Do NOT include <think>" in prompt


@pytest.mark.asyncio
async def test_run_voting_forces_configured_agent_name():
    agent = FakeAgent(
        name="Challenger",
        response_text='{"agent_name":"DevilsAdvocate","stance":"中立","reason":"需要补充边界","confidence":0.6}',
    )

    result = await run_voting(
        agents=[agent],
        topic="topic",
        discussion_context="final proposal",
        voting_prompt="vote",
    )

    assert result.votes[0].agent_name == "Challenger"


@pytest.mark.asyncio
async def test_sse_proxy_client_aggregates_sse_chunks(monkeypatch):
    client = SSEProxyAsyncOpenAI(api_key="xx", base_url="http://localhost:3030/v1")

    response = httpx.Response(
        200,
        text=(
            'data: {"id":"abc","choices":[{"delta":{"role":"assistant","content":""},"finish_reason":null,"index":0}],'
            '"created":123,"model":"gpt-5.4","object":"chat.completion.chunk","usage":null}\n\n'
            'data: {"id":"abc","choices":[{"delta":{"content":"Hello"},"finish_reason":null,"index":0}],'
            '"created":123,"model":"gpt-5.4","object":"chat.completion.chunk","usage":null}\n\n'
            'data: {"id":"abc","choices":[{"delta":{"content":" world"},"finish_reason":"stop","index":0}],'
            '"created":123,"model":"gpt-5.4","object":"chat.completion.chunk","usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}\n\n'
            "data: [DONE]\n\n"
        ),
        request=httpx.Request("POST", "http://localhost:3030/v1/chat/completions"),
    )

    async def fake_post(*args, **kwargs):
        return response

    monkeypatch.setattr(client._client, "post", fake_post)

    completion = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[{"role": "user", "content": "hi"}],
    )

    assert completion.choices[0].message.content == "Hello world"
    assert completion.choices[0].finish_reason == "stop"
    assert completion.model == "gpt-5.4"
    assert completion.usage.total_tokens == 3


def test_sse_proxy_parses_message_content_when_delta_content_missing():
    completion = _build_chat_completion_from_sse(
        (
            'data: {"id":"abc","choices":[{"message":{"role":"assistant","content":"Hello from message"},'
            '"finish_reason":"stop","index":0}],"created":123,"model":"gpt-5.4",'
            '"object":"chat.completion.chunk","usage":null}\n\n'
            "data: [DONE]\n\n"
        ),
        fallback_model="gpt-5.4",
    )

    assert completion.choices[0].message.content == "Hello from message"


@pytest.mark.asyncio
async def test_sse_proxy_stream_response_is_openai_async_stream_with_usage_attr(monkeypatch):
    client = SSEProxyAsyncOpenAI(api_key="xx", base_url="http://localhost:3030/v1")

    response = httpx.Response(
        200,
        text=(
            'data: {"id":"abc","choices":[{"delta":{"content":"Hello"},"finish_reason":"stop","index":0}],'
            '"created":123,"model":"gpt-5.4","object":"chat.completion.chunk","usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}\n\n'
            "data: [DONE]\n\n"
        ),
        request=httpx.Request("POST", "http://localhost:3030/v1/chat/completions"),
    )

    async def fake_post(*args, **kwargs):
        return response

    monkeypatch.setattr(client._client, "post", fake_post)

    stream = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )

    assert isinstance(stream, AsyncStream)
    assert hasattr(stream, "usage")
    assert stream.usage is None

    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    assert chunks[0].choices[0].delta.content == "Hello"


@pytest.mark.asyncio
async def test_run_pipeline_saves_report_after_confirmation(monkeypatch, tmp_path):
    config = _build_config()
    config.voting.enabled = True

    history = ChatHistory()
    history.add_message(ChatMessageContent(role=AuthorRole.USER, content="是否上线"))
    history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Architect", content="建议先灰度"))

    discussion_agent = FakeAgent(name="Debater")
    synthesizer = FakeAgent(name="Synthesizer", response_text="总结完成")

    async def fake_run_discussion(*args, **kwargs):
        return "总结完成", history

    async def fake_run_voting(*args, **kwargs):
        return SimpleNamespace(
            votes=[
                SimpleNamespace(agent_name="Debater", stance="赞成", reason="ok", confidence=0.9),
            ],
            conclusion="多数赞成（1 赞成 / 0 反对 / 0 中立）",
        )

    monkeypatch.setattr("src.pipeline.run_discussion", fake_run_discussion)
    monkeypatch.setattr("src.pipeline.run_followup", lambda *args, **kwargs: history)
    monkeypatch.setattr("src.pipeline.run_voting", fake_run_voting)
    monkeypatch.setattr("src.pipeline.create_service", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("src.pipeline.get_default_report_dir", lambda: tmp_path)

    created = [discussion_agent, synthesizer]

    def fake_create_agent(_config):
        return created.pop(0)

    monkeypatch.setattr("src.pipeline.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "y")

    await run_pipeline(config, "是否上线")

    reports = list(tmp_path.glob("*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "# 讨论报告" in content
    assert "是否上线" in content
    assert "总结完成" in content
    assert "多数赞成" in content


@pytest.mark.asyncio
async def test_run_discussion_uses_llm_group_chat_manager(monkeypatch, caplog):
    callback_messages: list[str] = []
    selected_agents: list[str] = []
    caplog.set_level(logging.INFO, logger="src.discussion")

    class FakeRuntime:
        def start(self):
            return None

        async def stop_when_idle(self):
            return None

    class FakeResult:
        async def get(self, timeout=None):
            return ChatMessageContent(role=AuthorRole.ASSISTANT, name="Host", content="最终摘要")

    captured: dict[str, object] = {}

    class FakeOrchestration:
        def __init__(self, members, manager, agent_response_callback):
            captured["members"] = members
            captured["manager"] = manager
            captured["callback"] = agent_response_callback

        async def invoke(self, task, runtime):
            await captured["callback"](  # type: ignore[index]
                ChatMessageContent(role=AuthorRole.ASSISTANT, name="Architect", content="专家发言")
            )
            return FakeResult()

    monkeypatch.setattr("src.discussion.GroupChatOrchestration", FakeOrchestration)
    monkeypatch.setattr("src.discussion.InProcessRuntime", FakeRuntime)

    agents = [FakeAgent(name="Architect"), FakeAgent(name="Pragmatist")]
    manager_service = create_service(
        AgentConfig(
            name="Proxy",
            description="proxy",
            instructions="proxy",
            service_type=ServiceType.OPENAI_SSE_PROXY,
            model="gpt-5.4",
            api_key="xx",
            base_url="http://localhost:3030/v1",
        )
    )
    summary, history = await run_discussion(
        agents=agents,  # type: ignore[arg-type]
        topic="测试话题",
        manager_service=manager_service,
        manager_name="Host",
        manager_instructions="主持人负责控场",
        max_rounds=3,
        response_callback=lambda msg: callback_messages.append(msg.content or ""),
        on_agent_selected=lambda name: selected_agents.append(name),
    )

    assert summary == "最终摘要"
    assert callback_messages == ["专家发言"]
    assert captured["members"] == agents
    assert isinstance(captured["manager"], LLMGroupChatManager)
    assert captured["manager"].facilitator_name == "Host"
    assert captured["manager"].facilitator_instructions == "主持人负责控场"
    assert captured["manager"].on_agent_selected is not None
    assert any(message.content == "专家发言" for message in history.messages)
    assert any(message.content == "最终摘要" for message in history.messages)
    assert "discussion.start" in caplog.text
    assert "agent.response name=Architect" in caplog.text
    assert "discussion.summary name=Host" in caplog.text


@pytest.mark.asyncio
async def test_managed_group_chat_falls_back_to_visible_transcript_on_timeout(monkeypatch):
    callback_messages: list[str] = []
    runtime_calls: list[str] = []

    class FakeRuntime:
        def start(self):
            return None

        async def stop(self):
            runtime_calls.append("stop")

        async def stop_when_idle(self):
            runtime_calls.append("stop_when_idle")

    class FakeResult:
        async def get(self, timeout=None):
            raise TimeoutError()

    class FakeOrchestration:
        def __init__(self, members, manager, agent_response_callback):
            self.agent_response_callback = agent_response_callback

        async def invoke(self, task, runtime):
            await self.agent_response_callback(
                ChatMessageContent(
                    role=AuthorRole.ASSISTANT,
                    name="Architect",
                    content="<think>hidden</think>可执行方案",
                )
            )
            await self.agent_response_callback(
                ChatMessageContent(
                    role=AuthorRole.ASSISTANT,
                    name="Challenger",
                    content="<think>",
                )
            )
            return FakeResult()

    monkeypatch.setattr("src.discussion.GroupChatOrchestration", FakeOrchestration)
    monkeypatch.setattr("src.discussion.InProcessRuntime", FakeRuntime)

    history = ChatHistory()
    history.add_message(ChatMessageContent(role=AuthorRole.USER, content="测试话题"))

    summary = await _run_managed_group_chat(
        agents=[FakeAgent(name="Architect"), FakeAgent(name="Challenger")],  # type: ignore[list-item]
        history=history,
        manager_service=create_service(
            AgentConfig(
                name="Proxy",
                description="proxy",
                instructions="proxy",
                service_type=ServiceType.OPENAI_SSE_PROXY,
                model="gpt-5.4",
                api_key="xx",
                base_url="http://localhost:3030/v1",
            )
        ),
        manager_name="Host",
        manager_instructions="",
        max_rounds=2,
        response_callback=lambda msg: callback_messages.append(msg.content or ""),
        supports_structured_output=False,
        selection_prompt="",
        termination_prompt="",
        result_filter_prompt="",
    )

    assert "可执行方案" in summary
    assert "<think>" not in summary
    assert callback_messages == ["可执行方案"]
    assert runtime_calls == ["stop"]


def test_brainstorm_finalize_keeps_complexity_and_dispatch_plan():
    session = BrainstormSession(
        config=BrainstormConfig(),
        kernel=SimpleNamespace(),
        service_id="test",
        on_question=lambda _payload: asyncio.Future(),
    )

    result = session._build_finalize_result(
        {
            "action": "finalize",
            "refined_topic": "精炼后的议题",
            "context_summary": "上下文摘要",
            "complexity": {
                "level": "medium",
                "rationale": "需要多角色拆解",
                "dimensions": ["技术判断", "落地风险"],
            },
            "dispatch_plan": {
                "tasks": [
                    {
                        "agent_name": "Architect",
                        "sub_topic": "评估架构影响",
                        "expected_output": "架构对比",
                    }
                ],
                "rationale": "先架构再落地",
            },
        },
        "原议题",
    )

    assert result["complexity"]["level"] == "medium"
    assert result["dispatch_plan"]["tasks"][0]["agent_name"] == "Architect"


def test_brainstorm_finalize_requires_structured_complexity_and_dispatch_plan():
    payload = json.dumps(
        {
            "action": "finalize",
            "refined_topic": "精炼后的议题",
            "context_summary": "上下文摘要",
        },
        ensure_ascii=False,
    )

    with pytest.raises(ValueError, match="complexity"):
        BrainstormSession._parse_llm_json(payload)


def test_brainstorm_force_finalize_returns_structured_complexity():
    session = BrainstormSession(
        config=BrainstormConfig(),
        kernel=SimpleNamespace(),
        service_id="test",
        on_question=lambda _payload: asyncio.Future(),
    )

    result = session._force_finalize("原议题", reason="parse_error")

    assert result["complexity"]["level"] == "medium"
    assert "解析" in result["complexity"]["rationale"]


@pytest.mark.asyncio
async def test_brainstorm_retry_adds_schema_repair_hint():
    class FakeBrainstormService:
        def __init__(self):
            self.calls: list[list[str]] = []

        async def get_chat_message_content(self, chat_history, settings):
            self.calls.append([message.content or "" for message in chat_history.messages])
            if len(self.calls) == 1:
                return ChatMessageContent(
                    role=AuthorRole.ASSISTANT,
                    content='{"action":"finalize","refined_topic":"精炼议题"}',
                )
            return ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content=json.dumps(
                    {
                        "action": "finalize",
                        "refined_topic": "精炼议题",
                        "context_summary": "摘要",
                        "complexity": {"level": "medium", "rationale": "需要结构化输出", "dimensions": []},
                        "dispatch_plan": {
                            "execution_mode": "panel",
                            "tasks": [],
                            "expected_final_output": "字段清单",
                            "rationale": "需要讨论",
                        },
                    },
                    ensure_ascii=False,
                ),
            )

    session = BrainstormSession(
        config=BrainstormConfig(),
        kernel=SimpleNamespace(),
        service_id="test",
        on_question=lambda _payload: asyncio.Future(),
    )
    service = FakeBrainstormService()

    result = await session._invoke_llm(service, "原议题", force_finalize=False)

    assert result["complexity"]["level"] == "medium"
    assert any("Previous brainstorm output was invalid" in message for message in service.calls[1])


@pytest.mark.asyncio
async def test_web_pipeline_emits_visible_moderator_question_and_uses_refined_topic(monkeypatch):
    from src import web_server

    class FakeWebSocket:
        def __init__(self):
            self.events: list[dict] = []

        async def send_text(self, data: str):
            self.events.append(json.loads(data))

    class FakeBrainstormSession:
        def __init__(self, config, kernel, service_id, on_question):
            self.on_question = on_question

        async def run(self, original_topic: str):
            await self.on_question(
                {
                    "id": "q-1",
                    "round": 1,
                    "max_rounds": 5,
                    "question": "需要先确认任务复杂度吗？",
                    "options": [{"id": "yes", "label": "需要"}],
                    "allow_multiple": False,
                    "allow_freeform": True,
                }
            )
            return {
                "refined_topic": "精炼议题",
                "context_summary": "摘要",
                "history": [],
                "complexity": {"level": "medium", "rationale": "需要拆给多角色"},
                "dispatch_plan": {
                    "tasks": [{"agent_name": "Expert", "sub_topic": "给出方案"}],
                    "rationale": "单专家先分析",
                },
            }

    config = AppConfig(
        agents=[
            AgentConfig(
                name="Host",
                description="主持人",
                instructions="控场",
                service_type=ServiceType.OPENAI,
                model="host-model",
                api_key="host-key",
            ),
            AgentConfig(
                name="Expert",
                description="专家",
                instructions="分析",
                service_type=ServiceType.OPENAI,
                model="expert-model",
                api_key="expert-key",
            ),
        ],
        discussion=DiscussionConfig(enabled=True, max_rounds=1),
        voting=VotingConfig(enabled=False),
        manager_service_index=0,
    )
    session = SimpleNamespace(
        config=config,
        history=ChatHistory(),
        discussion_transcript="",
        discussion_result=None,
        voting_result=None,
        manager_service=object(),
        manager_config=config.agents[0],
        discussion_agents=[FakeAgent(name="Expert")],
        final_agents=[],
    )
    ws = FakeWebSocket()
    captured: dict[str, str] = {}

    async def fake_run_discussion_phase(session, topic, callback, on_agent_selected=None, agents=None):
        captured["topic"] = topic
        history = ChatHistory()
        history.add_message(ChatMessageContent(role=AuthorRole.USER, content=topic))
        return "讨论摘要", history

    monkeypatch.setattr(web_server, "BrainstormSession", FakeBrainstormSession, raising=False)
    monkeypatch.setattr(web_server, "_run_discussion_phase", fake_run_discussion_phase)

    task = asyncio.create_task(
        web_server._run_session_pipeline(ws, session, "原议题", interaction_key="client-1")
    )
    try:
        for _ in range(50):
            if any(event.get("type") == "moderator_question" for event in ws.events):
                break
            await asyncio.sleep(0.01)

        assert any(event.get("type") == "phase" and event.get("phase") == "brainstorming" for event in ws.events)
        assert any(
            event.get("type") == "message"
            and event.get("name") == "Host"
            and event.get("phase") == "brainstorming"
            and "需要先确认任务复杂度吗？" in event.get("content", "")
            for event in ws.events
        )

        answer_future = web_server.pending_brainstorm_answers["client-1"]
        answer_future.set_result("需要")

        for _ in range(50):
            if any(event.get("type") == "topic_refined" for event in ws.events):
                break
            await asyncio.sleep(0.01)

        assert any(
            event.get("type") == "message"
            and event.get("name") == "Host"
            and event.get("meta", {}).get("variant") == "dispatch"
            for event in ws.events
        )

        if hasattr(web_server, "pending_topic_confirmations"):
            confirm_future = web_server.pending_topic_confirmations.get("client-1")
            if confirm_future is not None and not confirm_future.done():
                confirm_future.set_result("confirm")

        await asyncio.wait_for(task, timeout=1)
    finally:
        if not task.done():
            task.cancel()

    assert "精炼议题" in captured["topic"]


@pytest.mark.asyncio
async def test_web_pipeline_focused_dispatch_runs_only_selected_agent(monkeypatch):
    from src import web_server

    class FakeWebSocket:
        def __init__(self):
            self.events: list[dict] = []

        async def send_text(self, data: str):
            self.events.append(json.loads(data))

    class FakeBrainstormSession:
        def __init__(self, config, kernel, service_id, on_question):
            pass

        async def run(self, original_topic: str):
            return {
                "refined_topic": "精炼议题",
                "context_summary": "摘要",
                "history": [],
                "complexity": {"level": "medium", "rationale": "单角色足够"},
                "dispatch_plan": {
                    "execution_mode": "focused",
                    "tasks": [
                        {"agent_name": "Architect", "sub_topic": "输出结构化工单字段"},
                        {"agent_name": "Ghost", "sub_topic": "不存在"},
                    ],
                    "expected_final_output": "安全工单内容清单",
                },
            }

    config = AppConfig(
        agents=[
            AgentConfig(
                name="Host",
                description="主持人",
                instructions="控场",
                service_type=ServiceType.OPENAI,
                model="host-model",
                api_key="host-key",
            ),
            AgentConfig(
                name="Architect",
                description="架构师",
                instructions="分析结构",
                service_type=ServiceType.OPENAI,
                model="architect-model",
                api_key="architect-key",
            ),
            AgentConfig(
                name="Pragmatist",
                description="务实派",
                instructions="分析落地",
                service_type=ServiceType.OPENAI,
                model="pragmatist-model",
                api_key="pragmatist-key",
            ),
            AgentConfig(
                name="Synthesizer",
                description="总结",
                instructions="总结",
                service_type=ServiceType.OPENAI,
                model="sum-model",
                api_key="sum-key",
                final_only=True,
            ),
        ],
        discussion=DiscussionConfig(enabled=True, max_rounds=2),
        voting=VotingConfig(enabled=True),
        manager_service_index=0,
    )
    architect = FakeAgent(name="Architect")
    pragmatist = FakeAgent(name="Pragmatist")
    synthesizer = FakeAgent(name="Synthesizer", response_text="最终方案：字段清单")
    session = SimpleNamespace(
        config=config,
        history=ChatHistory(),
        discussion_transcript="",
        discussion_result=None,
        voting_result=None,
        final_solution=None,
        review_result=None,
        dispatch_state=None,
        manager_service=object(),
        manager_config=config.agents[0],
        discussion_agents=[architect, pragmatist],
        final_agents=[(config.agents[3], synthesizer)],
    )
    captured: dict[str, object] = {}

    async def fake_run_discussion_phase(session, topic, callback, on_agent_selected=None, agents=None):
        captured["discussion_agents"] = [agent.name for agent in agents]
        callback(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Architect", content="字段要分层"))
        history = ChatHistory()
        history.add_message(ChatMessageContent(role=AuthorRole.USER, content=topic))
        history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Architect", content="字段要分层"))
        return "讨论摘要", history

    async def fake_run_voting(*, agents, discussion_context, **kwargs):
        captured["voting_agents"] = [agent.name for agent in agents]
        captured["review_context"] = discussion_context
        return SimpleNamespace(
            votes=[SimpleNamespace(agent_name="Architect", stance="赞成", reason="ok", confidence=0.8)],
            conclusion="多数赞成（1 赞成 / 0 反对 / 0 中立）",
        )

    monkeypatch.setattr(web_server, "BrainstormSession", FakeBrainstormSession, raising=False)
    monkeypatch.setattr(web_server, "_run_discussion_phase", fake_run_discussion_phase)
    monkeypatch.setattr(web_server, "run_voting", fake_run_voting)

    ws = FakeWebSocket()
    task = asyncio.create_task(
        web_server._run_session_pipeline(ws, session, "原议题", interaction_key="focused-client")
    )
    try:
        for _ in range(50):
            confirm_future = web_server.pending_topic_confirmations.get("focused-client")
            if confirm_future is not None:
                confirm_future.set_result("confirm")
                break
            await asyncio.sleep(0.01)

        await asyncio.wait_for(task, timeout=1)
    finally:
        if not task.done():
            task.cancel()

    assert captured["discussion_agents"] == ["Architect"]
    assert captured["voting_agents"] == ["Architect"]
    assert captured["review_context"] == "最终方案：字段清单"
    assert any(event.get("type") == "summary" and event.get("content") == "最终方案：字段清单" for event in ws.events)
    assert not any(event.get("type") == "message" and event.get("name") == "Pragmatist" for event in ws.events)


@pytest.mark.asyncio
async def test_web_pipeline_direct_mode_skips_discussion_and_emits_final_solution(monkeypatch):
    from src import web_server

    class FakeWebSocket:
        def __init__(self):
            self.events: list[dict] = []

        async def send_text(self, data: str):
            self.events.append(json.loads(data))

    class FakeBrainstormSession:
        def __init__(self, config, kernel, service_id, on_question):
            pass

        async def run(self, original_topic: str):
            return {
                "refined_topic": "精炼议题",
                "context_summary": "",
                "history": [],
                "complexity": {"level": "low", "rationale": "直接总结即可"},
                "dispatch_plan": {
                    "execution_mode": "direct",
                    "tasks": [],
                    "expected_final_output": "安全工单字段清单",
                },
            }

    config = AppConfig(
        agents=[
            AgentConfig(
                name="Host",
                description="主持人",
                instructions="控场",
                service_type=ServiceType.OPENAI,
                model="host-model",
                api_key="host-key",
            ),
            AgentConfig(
                name="Architect",
                description="架构师",
                instructions="分析",
                service_type=ServiceType.OPENAI,
                model="architect-model",
                api_key="architect-key",
            ),
            AgentConfig(
                name="Synthesizer",
                description="总结",
                instructions="总结",
                service_type=ServiceType.OPENAI,
                model="sum-model",
                api_key="sum-key",
                final_only=True,
            ),
        ],
        discussion=DiscussionConfig(enabled=True, max_rounds=2),
        voting=VotingConfig(enabled=True),
        manager_service_index=0,
    )
    synthesizer = FakeAgent(name="Synthesizer", response_text="最终方案：直接字段清单")
    session = SimpleNamespace(
        config=config,
        history=ChatHistory(),
        discussion_transcript="",
        discussion_result=None,
        voting_result=None,
        final_solution=None,
        review_result=None,
        dispatch_state=None,
        manager_service=object(),
        manager_config=config.agents[0],
        discussion_agents=[FakeAgent(name="Architect")],
        final_agents=[(config.agents[2], synthesizer)],
    )

    async def fail_run_discussion_phase(*args, **kwargs):
        raise AssertionError("direct mode should not run discussion")

    async def fail_run_voting(*args, **kwargs):
        raise AssertionError("direct mode has no selected reviewers")

    monkeypatch.setattr(web_server, "BrainstormSession", FakeBrainstormSession, raising=False)
    monkeypatch.setattr(web_server, "_run_discussion_phase", fail_run_discussion_phase)
    monkeypatch.setattr(web_server, "run_voting", fail_run_voting)

    ws = FakeWebSocket()
    task = asyncio.create_task(
        web_server._run_session_pipeline(ws, session, "原议题", interaction_key="direct-client")
    )
    try:
        for _ in range(50):
            confirm_future = web_server.pending_topic_confirmations.get("direct-client")
            if confirm_future is not None:
                confirm_future.set_result("confirm")
                break
            await asyncio.sleep(0.01)

        await asyncio.wait_for(task, timeout=1)
    finally:
        if not task.done():
            task.cancel()

    assert any(event.get("type") == "summary" and event.get("content") == "最终方案：直接字段清单" for event in ws.events)
    assert not any(event.get("type") == "phase" and event.get("phase") == "discussion" for event in ws.events)


@pytest.mark.asyncio
async def test_pipeline_excludes_host_from_discussion_and_voting(monkeypatch):
    config = AppConfig(
        agents=[
            AgentConfig(
                name="Host",
                description="主持人",
                instructions="控场",
                service_type=ServiceType.OPENAI,
                model="host-model",
                api_key="host-key",
            ),
            AgentConfig(
                name="Expert",
                description="专家",
                instructions="分析",
                service_type=ServiceType.OPENAI,
                model="expert-model",
                api_key="expert-key",
            ),
            AgentConfig(
                name="Synthesizer",
                description="总结",
                instructions="总结",
                service_type=ServiceType.OPENAI,
                model="sum-model",
                api_key="sum-key",
                final_only=True,
            ),
        ],
        discussion=DiscussionConfig(enabled=True, max_rounds=2),
        voting=VotingConfig(enabled=True),
        manager_service_index=0,
    )

    call_record: dict[str, list[str]] = {}
    history = ChatHistory()
    history.add_message(ChatMessageContent(role=AuthorRole.USER, content="topic"))
    history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Expert", content="专家观点"))

    host_agent = FakeAgent(name="Host")
    expert_agent = FakeAgent(name="Expert", response_text="专家观点")
    synthesizer = FakeAgent(name="Synthesizer", response_text="总结完成")
    created = {
        "Host": host_agent,
        "Expert": expert_agent,
        "Synthesizer": synthesizer,
    }

    def fake_create_agent(config):
        return created[config.name]

    async def fake_run_discussion(*, agents, manager_name, manager_instructions, **kwargs):
        call_record["discussion_agents"] = [agent.name for agent in agents]
        call_record["manager_name"] = manager_name
        call_record["manager_instructions"] = manager_instructions
        return "讨论摘要", history

    async def fake_run_voting(*, agents, **kwargs):
        call_record["voting_agents"] = [agent.name for agent in agents]
        return SimpleNamespace(
            votes=[SimpleNamespace(agent_name="Expert", stance="赞成", reason="ok", confidence=0.8)],
            conclusion="多数赞成（1 赞成 / 0 反对 / 0 中立）",
        )

    monkeypatch.setattr("src.pipeline.create_agent", fake_create_agent)
    monkeypatch.setattr("src.pipeline.create_service", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("src.pipeline.run_discussion", fake_run_discussion)
    monkeypatch.setattr("src.pipeline.run_voting", fake_run_voting)
    monkeypatch.setattr("src.pipeline.run_followup", lambda *args, **kwargs: history)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "q")

    await run_pipeline(config, "topic")

    assert call_record["discussion_agents"] == ["Expert"]
    assert call_record["voting_agents"] == ["Expert"]
    assert call_record["manager_name"] == "Host"
    assert call_record["manager_instructions"] == "控场"
