from pathlib import Path

import pytest

from src.loader import load_config, resolve_env_vars, resolve_preset
from src.models import AgentConfig, AppConfig, PresetConfig, ServiceType


def test_resolve_env_vars_allows_empty_default(monkeypatch):
    monkeypatch.delenv("MISSING_OPTIONAL_KEY", raising=False)

    assert resolve_env_vars("${MISSING_OPTIONAL_KEY:-}") == ""


def test_resolve_env_vars_keeps_missing_required_vars_strict(monkeypatch):
    monkeypatch.delenv("MISSING_REQUIRED_KEY", raising=False)

    with pytest.raises(ValueError, match="MISSING_REQUIRED_KEY"):
        resolve_env_vars("${MISSING_REQUIRED_KEY}")


def test_config_allows_empty_sse_proxy_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_SSE_PROXY_API_KEY", raising=False)
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """
agents:
  - name: Host
    description: host
    instructions: host
    model: gpt-test
    service_type: openai_sse_proxy
    api_key: "${OPENAI_SSE_PROXY_API_KEY:-}"
    base_url: "http://localhost:3030/v1"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(str(config_path))

    assert config.agents[0].api_key == "${OPENAI_SSE_PROXY_API_KEY:-}"


def test_all_builtin_configs_load(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    for config_path in (Path(__file__).resolve().parents[1] / "src" / "config").glob("*.yaml"):
        config = load_config(str(config_path))
        assert config.agents, f"{config_path} should define agents"


def test_preset_config_is_additive_and_resolves_discussion_agents():
    config = AppConfig(
        agents=[
            AgentConfig(name="Host", description="host", instructions="host", model="host-model"),
            AgentConfig(name="Architect", description="arch", instructions="arch", model="arch-model"),
            AgentConfig(name="Pragmatist", description="pm", instructions="pm", model="pm-model"),
            AgentConfig(name="Challenger", description="risk", instructions="risk", model="risk-model"),
            AgentConfig(
                name="Synthesizer",
                description="summary",
                instructions="summary",
                model="sum-model",
                final_only=True,
            ),
        ],
        manager_service_index=0,
        presets={
            "architecture_review": PresetConfig(
                label="架构评审",
                description="系统设计、可行性评估、假设验证",
                agents=["Architect", "Pragmatist", "Challenger"],
            )
        },
        default_preset="architecture_review",
    )

    resolved = resolve_preset(config)

    assert [agent.name for agent in resolved] == ["Architect", "Pragmatist", "Challenger"]


def test_load_config_rejects_presets_that_reference_manager_or_final_agent(tmp_path):
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """
manager_service_index: 0
agents:
  - name: Host
    description: host
    instructions: host
    model: host-model
  - name: Architect
    description: arch
    instructions: arch
    model: arch-model
  - name: Pragmatist
    description: pm
    instructions: pm
    model: pm-model
  - name: Synthesizer
    description: summary
    instructions: summary
    model: sum-model
    final_only: true
default_preset: broken
presets:
  broken:
    label: Broken
    description: Invalid references
    agents: [Host, Architect, Synthesizer]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot reference"):
        load_config(str(config_path))


def test_load_config_rejects_duplicate_preset_agents(tmp_path):
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """
manager_service_index: 0
agents:
  - name: Host
    description: host
    instructions: host
    model: host-model
  - name: Architect
    description: arch
    instructions: arch
    model: arch-model
  - name: Pragmatist
    description: pm
    instructions: pm
    model: pm-model
  - name: Challenger
    description: risk
    instructions: risk
    model: risk-model
default_preset: duplicate
presets:
  duplicate:
    label: Duplicate
    description: Duplicate agent names
    agents: [Architect, Architect, Pragmatist]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_config(str(config_path))
