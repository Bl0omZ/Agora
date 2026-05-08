import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

from src.models import (
    AgentConfig,
    AppConfig,
    BrainstormConfig,
    DiscussionConfig,
    ServiceType,
    VotingConfig,
)
from src.web_server import _run_synthesis_phase


class FakeAgent:
    def __init__(self, name: str, response_text: str):
        self.name = name
        self.response_text = response_text

    async def get_response(self, messages=None, **kwargs):
        return SimpleNamespace(
            message=ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                name=self.name,
                content=self.response_text,
            )
        )


class FakeWebSocket:
    def __init__(self):
        self.events: list[dict] = []

    async def send_text(self, data: str):
        self.events.append(json.loads(data))


@pytest.mark.asyncio
async def test_minimal_synthesizer_outputs_discussion_summary():
    output = {
        "schema_version": 2,
        "participants": [
            {
                "name": "Architect",
                "role": "架构师",
                "model": "mimo-pro",
                "is_moderator": False,
                "message_count": 1,
                "key_points": ["建议方案 A"],
            },
            {
                "name": "Pragmatist",
                "role": "落地派",
                "model": "mimo-pro",
                "is_moderator": False,
                "message_count": 1,
                "key_points": ["先做 MVP"],
            },
            {
                "name": "Challenger",
                "role": "挑战者",
                "model": "mimo-pro",
                "is_moderator": False,
                "message_count": 1,
                "key_points": ["验证关键假设"],
            },
        ],
        "distilled_conclusion": "建议采用方案 A，先以 MVP 验证关键假设。",
        "degraded": False,
        "degraded_reason": None,
    }
    config = AppConfig(
        agents=[
            AgentConfig(
                name="Host",
                description="主持人",
                instructions="控场",
                service_type=ServiceType.OPENAI,
                model="host-model",
                api_key="test-key",
            ),
            AgentConfig(name="Architect", description="架构师", instructions="arch", model="mimo-pro"),
            AgentConfig(name="Pragmatist", description="落地派", instructions="pm", model="mimo-pro"),
            AgentConfig(name="Challenger", description="挑战者", instructions="risk", model="mimo-pro"),
            AgentConfig(
                name="Synthesizer",
                description="总结者",
                instructions="summary",
                model="mimo-pro",
                final_only=True,
            ),
        ],
        brainstorm=BrainstormConfig(enabled=False),
        discussion=DiscussionConfig(enabled=False),
        voting=VotingConfig(enabled=False),
        manager_service_index=0,
    )
    session = SimpleNamespace(
        config=config,
        history=ChatHistory(),
        discussion_transcript="",
        discussion_result=None,
        final_solution=None,
        dispatch_state={"selected_agents": ["Architect", "Pragmatist", "Challenger"]},
        manager_config=config.agents[0],
        final_agents=[],
    )
    for name, content in [
        ("Architect", "我建议方案 A"),
        ("Pragmatist", "可以先做 MVP"),
        ("Challenger", "要验证关键假设"),
    ]:
        session.history.add_message(
            ChatMessageContent(role=AuthorRole.ASSISTANT, name=name, content=content)
        )
    session.discussion_transcript = "\n".join(
        f"[{name}] {content}"
        for name, content in [
            ("Architect", "我建议方案 A"),
            ("Pragmatist", "可以先做 MVP"),
            ("Challenger", "要验证关键假设"),
        ]
    )
    session.final_agents = [(config.agents[-1], FakeAgent("Synthesizer", json.dumps(output, ensure_ascii=False)))]
    ws = FakeWebSocket()

    await _run_synthesis_phase(ws, session, "是否采用方案 A")

    event = next(item for item in ws.events if item["type"] == "discussion_summary")
    actual = event["summary"]
    assert actual == output
    output_path = Path(".omc/plans/fixtures/codex_synthesizer_minimal_output.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding="utf-8")
