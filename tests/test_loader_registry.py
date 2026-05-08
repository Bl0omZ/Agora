import logging
from pathlib import Path

import yaml

from src.loader import load_config, resolve_agent_runtime_config


def test_load_config_keeps_empty_registry_backward_compatible(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    path = tmp_path / "agents.yaml"
    path.write_text(
        yaml.safe_dump({
            "models": [],
            "manager_service_index": 0,
            "agents": [
                {
                    "name": "Host",
                    "description": "host",
                    "instructions": "host",
                    "model": "legacy-host",
                    "api_key": "${OPENAI_API_KEY}",
                    "base_url": "https://legacy.example/v1",
                }
            ],
        }, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    config = load_config(str(path))

    assert config.models == []
    assert config.agents[0].model == "legacy-host"
    assert config.agents[0].base_url == "https://legacy.example/v1"


def test_registry_hit_overrides_inline_fields_and_warns(monkeypatch, tmp_path: Path, caplog):
    monkeypatch.setenv("REGISTRY_KEY", "test-key")
    path = tmp_path / "agents.yaml"
    path.write_text(
        yaml.safe_dump({
            "models": [
                {
                    "name": "mimo-pro",
                    "provider": "openai-compatible",
                    "base_url": "https://registry.example/v1",
                    "models": [{"id": "real-model"}],
                    "env_var_name": "REGISTRY_KEY",
                }
            ],
            "manager_service_index": 0,
            "agents": [
                {
                    "name": "Host",
                    "description": "host",
                    "instructions": "host",
                    "model": "mimo-pro/real-model",
                    "api_key": "${INLINE_KEY:-}",
                    "base_url": "https://inline.example/v1",
                }
            ],
        }, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    config = load_config(str(path))
    with caplog.at_level(logging.WARNING, logger="src.loader"):
        runtime = resolve_agent_runtime_config(config, config.agents[0])

    assert runtime.model == "real-model"
    assert runtime.base_url == "https://registry.example/v1"
    assert runtime.api_key == "${REGISTRY_KEY:-}"
    assert "inline base_url/api_key ignored" in caplog.text
