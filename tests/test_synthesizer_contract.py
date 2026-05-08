import json
from types import SimpleNamespace

import pytest

from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

from src.models import AgentConfig, AppConfig, DiscussionSummary
from src.web_server import _parse_discussion_summary_json, _run_synthesis_phase


class FakeAgent:
    def __init__(self, name: str, responses: list[str]):
        self.name = name
        self.responses = responses
        self.prompts: list[str] = []

    async def get_response(self, messages=None, **kwargs):
        self.prompts.append(messages[0].content)
        content = self.responses.pop(0)
        return SimpleNamespace(
            message=ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                name=self.name,
                content=content,
            )
        )


class FakeWebSocket:
    def __init__(self):
        self.events: list[dict] = []

    async def send_text(self, data: str):
        self.events.append(json.loads(data))


def _session(fake_agent: FakeAgent):
    config = AppConfig(
        agents=[
            AgentConfig(name="Host", description="主持人", instructions="host", model="host-model"),
            AgentConfig(name="Architect", description="架构师", instructions="arch", model="model-a"),
            AgentConfig(
                name="Synthesizer",
                description="总结者",
                instructions="summary",
                model="summary-model",
                final_only=True,
            ),
        ],
        manager_service_index=0,
    )
    history = ChatHistory()
    history.add_message(ChatMessageContent(role=AuthorRole.ASSISTANT, name="Architect", content="先做 MVP"))
    return SimpleNamespace(
        config=config,
        history=history,
        discussion_transcript="[Architect] 先做 MVP",
        discussion_result=None,
        final_solution=None,
        dispatch_state={"selected_agents": ["Architect"]},
        manager_config=config.agents[0],
        final_agents=[(config.agents[-1], fake_agent)],
    )


def test_discussion_summary_schema_rejects_stance_confidence_contract():
    summary = DiscussionSummary.model_validate({
        "schema_version": 2,
        "participants": [
            {
                "name": "Architect",
                "role": "架构师",
                "model": "model-a",
                "is_moderator": False,
                "message_count": 1,
                "key_points": ["先做 MVP"],
            }
        ],
        "distilled_conclusion": "先做 MVP。",
        "degraded": False,
        "degraded_reason": None,
    })

    assert "stance" not in summary.participants[0].model_dump()
    assert "confidence" not in summary.participants[0].model_dump()


@pytest.mark.asyncio
async def test_synthesizer_retries_invalid_json_then_emits_summary():
    valid = json.dumps({
        "schema_version": 2,
        "participants": [
            {
                "name": "Architect",
                "role": "架构师",
                "model": "model-a",
                "is_moderator": False,
                "message_count": 1,
                "key_points": ["先做 MVP"],
            }
        ],
        "distilled_conclusion": "先做 MVP。",
        "degraded": False,
        "degraded_reason": None,
    }, ensure_ascii=False)
    agent = FakeAgent("Synthesizer", ["不是 JSON", valid])
    ws = FakeWebSocket()

    await _run_synthesis_phase(ws, _session(agent), "议题")

    event = next(item for item in ws.events if item["type"] == "discussion_summary")
    assert event["summary"]["distilled_conclusion"] == "先做 MVP。"
    assert "上次输出非法 JSON" in agent.prompts[1]


def test_parse_discussion_summary_accepts_raw_json_only():
    parsed = _parse_discussion_summary_json(json.dumps({
        "schema_version": 2,
        "participants": [],
        "distilled_conclusion": "结论",
        "degraded": False,
        "degraded_reason": None,
    }, ensure_ascii=False))

    assert parsed.distilled_conclusion == "结论"
