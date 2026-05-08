import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src import web_server
from src.config_writer import compute_etag


def _config_path(tmp_path: Path) -> Path:
    raw = {
        "models": [
            {
                "name": "mimo",
                "provider": "openai-compatible",
                "base_url": "https://example.api/v1",
                "models": ["mimo-pro"],
                "env_var_name": "OPENAI_API_KEY",
            }
        ],
        "manager_service_index": 0,
        "summary_model": None,
        "agents": [
            {
                "name": "Host",
                "description": "主持人",
                "instructions": "host",
                "model": "mimo/mimo-pro",
                "api_key": "${OPENAI_API_KEY:-}",
                "base_url": "https://inline.example/v1",
            },
            {
                "name": "Architect",
                "description": "架构师",
                "instructions": "arch",
                "model": "legacy-model",
                "api_key": "${OPENAI_API_KEY:-}",
                "base_url": "https://legacy.example/v1",
            },
            {
                "name": "Pragmatist",
                "description": "落地派",
                "instructions": "pm",
                "model": "legacy-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
            {
                "name": "Challenger",
                "description": "挑战者",
                "instructions": "risk",
                "model": "legacy-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
        ],
        "default_preset": "default",
        "presets": {
            "default": {
                "label": "默认讨论组",
                "description": "默认",
                "agents": ["Architect", "Pragmatist", "Challenger"],
            }
        },
        "discussion": {"enabled": True, "max_rounds": 4},
        "brainstorm": {"enabled": True},
        "voting": {"enabled": True, "per_agent_timeout_s": 120},
    }
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def client(monkeypatch, tmp_path):
    path = _config_path(tmp_path)
    monkeypatch.setattr(web_server, "_default_config_path", lambda: str(path))
    return TestClient(web_server.app), path


def test_get_config_returns_public_payload_and_etag(client):
    test_client, path = client

    response = test_client.get("/api/config")

    assert response.status_code == 200
    assert response.headers["etag"] == compute_etag(path.read_bytes())
    text = response.text
    assert "api_key" not in text
    assert "secret" not in text
    assert "token" not in text
    payload = response.json()
    assert set(payload) == {"models", "agents", "presets", "runtime"}
    assert payload["models"][0]["env_var_name"] == "OPENAI_API_KEY"
    assert payload["runtime"]["summary_model"] is None


def test_get_config_subroutes_are_sanitized(client):
    test_client, _path = client
    for route, key in [
        ("/api/config/models", "models"),
        ("/api/config/agents", "agents"),
        ("/api/config/presets", "presets"),
        ("/api/config/runtime", "runtime"),
    ]:
        response = test_client.get(route)
        assert response.status_code == 200
        assert key in response.json()
        assert "api_key" not in response.text


def test_put_requires_current_etag(client):
    test_client, _path = client

    response = test_client.put("/api/config/runtime", json={"max_rounds": 5})

    assert response.status_code == 409
    assert response.json()["error"]["detail"] == "config_modified_elsewhere"


def test_put_empty_models_keeps_original_file(client):
    test_client, path = client
    before = path.read_text(encoding="utf-8")
    etag = test_client.get("/api/config").headers["etag"]
    models = test_client.get("/api/config/models").json()["models"]
    models[0]["models"] = []

    response = test_client.put("/api/config/models", headers={"If-Match": etag}, json=models)

    assert response.status_code == 422
    assert "models" in response.text
    assert path.read_text(encoding="utf-8") == before


def test_put_runtime_validates_summary_model(client):
    test_client, _path = client
    etag = test_client.get("/api/config").headers["etag"]

    response = test_client.put(
        "/api/config/runtime",
        headers={"If-Match": etag},
        json={
            "max_rounds": 5,
            "brainstorm_enabled": True,
            "voting_timeout_s": 90,
            "summary_model": "missing",
        },
    )

    assert response.status_code == 422
    assert "summary_model" in response.text


def test_put_agents_sanitizes_inline_model_fields(client):
    test_client, path = client
    etag = test_client.get("/api/config").headers["etag"]
    agents = test_client.get("/api/config/agents").json()["agents"]
    agents[1]["model"] = "mimo/mimo-pro"

    response = test_client.put("/api/config/agents", headers={"If-Match": etag}, json=agents)

    assert response.status_code == 200
    assert response.json()["sanitized_fields"] == [
        {"agent_name": "Host", "sanitized_fields": ["base_url", "api_key"]},
        {"agent_name": "Architect", "sanitized_fields": ["base_url", "api_key"]},
    ]
    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    architect = next(agent for agent in written["agents"] if agent["name"] == "Architect")
    assert "base_url" not in architect
    assert "api_key" not in architect


def test_export_config_does_not_include_secret_fields(client):
    test_client, _path = client

    response = test_client.get("/api/config/export")

    assert response.status_code == 200
    assert "api_key" not in response.text
    assert "OPENAI_API_KEY" in response.text
