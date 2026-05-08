import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src import web_server

SENTINEL = "SENTINEL_KEY_8e7f6a5b"


def _write_config(path: Path) -> None:
    raw = {
        "models": [
            {
                "name": "sentinel-model",
                "provider": "openai-compatible",
                "base_url": "https://example.api/v1",
                "model_id": "safe-model-id",
                "env_var_name": "OPENAI_API_KEY",
            }
        ],
        "manager_service_index": 0,
        "agents": [
            {
                "name": "Host",
                "description": "主持人",
                "instructions": "host",
                "model": "sentinel-model",
                "api_key": "${OPENAI_API_KEY:-}",
                "base_url": "https://inline.example/v1",
            },
            {
                "name": "Architect",
                "description": "架构师",
                "instructions": "arch",
                "model": "sentinel-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
            {
                "name": "Pragmatist",
                "description": "落地派",
                "instructions": "pm",
                "model": "sentinel-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
            {
                "name": "Challenger",
                "description": "挑战者",
                "instructions": "risk",
                "model": "sentinel-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
        ],
        "default_preset": "default",
        "presets": {
            "default": {
                "label": "默认",
                "description": "默认讨论组",
                "agents": ["Architect", "Pragmatist", "Challenger"],
            }
        },
        "discussion": {"enabled": False, "max_rounds": 1},
        "brainstorm": {"enabled": False},
        "voting": {"enabled": False, "per_agent_timeout_s": 120},
    }
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", SENTINEL)
    config_path = tmp_path / "agents.yaml"
    _write_config(config_path)
    monkeypatch.setattr(web_server, "_default_config_path", lambda: str(config_path))

    async def fake_pipeline(websocket, session, topic, interaction_key=None):
        await web_server._send_json(websocket, {"type": "started", "topic": topic})
        await web_server._send_json(websocket, {
            "type": "discussion_summary",
            "phase": "synthesis",
            "schema_version": 2,
            "summary": {
                "schema_version": 2,
                "participants": [],
                "distilled_conclusion": "安全测试结论",
                "degraded": False,
                "degraded_reason": None,
            },
        })
        await web_server._send_json(websocket, {"type": "ready"})

    monkeypatch.setattr(web_server, "_run_session_pipeline", fake_pipeline)
    return TestClient(web_server.app)


def test_no_sentinel_key_leaks_from_config_gets_or_ws(client):
    responses = []
    for route in [
        "/api/config",
        "/api/config/models",
        "/api/config/agents",
        "/api/config/presets",
        "/api/config/runtime",
        "/api/config/export",
    ]:
        response = client.get(route)
        assert response.status_code == 200
        responses.append(response.text)

    ws_events = []
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(json.dumps({"type": "start", "topic": "安全测试"}, ensure_ascii=False))
        while True:
            event = json.loads(websocket.receive_text())
            ws_events.append(event)
            if event.get("type") == "ready":
                break

    dumped = json.dumps(responses + ws_events, ensure_ascii=False)
    assert "discussion_summary" in dumped
    assert SENTINEL not in dumped
