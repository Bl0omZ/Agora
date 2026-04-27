import pytest

from src.loader import load_config, resolve_env_vars


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
