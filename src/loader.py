"""YAML configuration loading, environment variable resolution, and service/agent factories."""

import logging
import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIChatCompletion

from .models import AgentConfig, AppConfig, ServiceType
from .openai_sse_proxy import SSEProxyAsyncOpenAI

logger = logging.getLogger(__name__)

SCOPE_CONSTRAINT = """
---
**范围约束（强制执行）：**
- 严格围绕用户的议题范围作答。不主动展开到议题未涉及的领域
- 回答的深度和广度必须匹配议题本身的粒度
- 如果你的专业视角与当前议题不直接相关，先说明关联性，等主持人确认后再展开
- 当主持人指出你偏离议题时，立即收回并聚焦
- 每次发言不超过 300 字
"""


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without adding a runtime dependency."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("'\"")


def _load_local_env(config_path: str) -> None:
    candidates = [Path.cwd() / ".env"]
    for parent in Path(config_path).resolve().parents:
        candidates.append(parent / ".env")
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        _load_dotenv(candidate)


def resolve_env_vars(value: str | None) -> str | None:
    """Resolve ${ENV_VAR} and ${ENV_VAR:-default} references in a string."""
    if value is None:
        return None
    pattern = r"\$\{(\w+)(?::-(.*?))?\}"

    def replacer(match: re.Match[str]) -> str:
        env_key = match.group(1)
        default = match.group(2)
        env_val = os.environ.get(env_key)
        if env_val is None:
            if default is not None:
                return default
            raise ValueError(f"Environment variable '{env_key}' is not set. Required by config.")
        return env_val

    return re.sub(pattern, replacer, value)


def load_config(path: str) -> AppConfig:
    """Load and validate configuration from a YAML file."""
    _load_local_env(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Config file '{path}' is empty.")

    try:
        config = AppConfig(**raw)
    except ValidationError as e:
        raise ValueError(f"Invalid config in '{path}':\n{e}") from e
    _validate_presets(config)

    # Validate environment variables are available
    for agent in config.agents:
        resolve_env_vars(agent.api_key)
        resolve_env_vars(agent.base_url)
        resolve_env_vars(agent.endpoint)

    return config


def _discussion_agent_configs(config: AppConfig) -> list[AgentConfig]:
    return [
        agent
        for index, agent in enumerate(config.agents)
        if index != config.manager_service_index and not agent.final_only
    ]


def _validate_presets(config: AppConfig) -> None:
    """Validate optional preset configuration against the flat agent list."""
    if not config.presets:
        return
    if not config.default_preset:
        raise ValueError("default_preset is required when presets are configured.")
    if config.default_preset not in config.presets:
        raise ValueError(
            f"default_preset '{config.default_preset}' is not defined in presets. "
            f"Available: {list(config.presets.keys())}"
        )

    allowed_names = {agent.name for agent in _discussion_agent_configs(config)}
    for preset_name, preset in config.presets.items():
        if len(preset.agents) != 3:
            raise ValueError(
                f"Preset '{preset_name}' must reference exactly 3 discussion agents, "
                f"got {len(preset.agents)}."
            )
        if len(set(preset.agents)) != len(preset.agents):
            raise ValueError(f"Preset '{preset_name}' contains duplicate agent names.")
        invalid = [name for name in preset.agents if name not in allowed_names]
        if invalid:
            raise ValueError(
                f"Preset '{preset_name}' cannot reference manager/final/unknown agents: {invalid}. "
                f"Available discussion agents: {sorted(allowed_names)}"
            )


def resolve_preset(config: AppConfig, preset_name: str | None = None) -> list[AgentConfig]:
    """Return discussion agent configs for the requested preset.

    If no presets are configured, return all current discussion agents for
    backward compatibility with legacy configs.
    """
    if not config.presets:
        return _discussion_agent_configs(config)

    name = preset_name or config.default_preset
    if not name or name not in config.presets:
        raise ValueError(f"Unknown preset '{name}'. Available: {list(config.presets.keys())}")

    agent_map = {agent.name: agent for agent in _discussion_agent_configs(config)}
    return [agent_map[agent_name] for agent_name in config.presets[name].agents]


def create_service(config: AgentConfig) -> ChatCompletionClientBase:
    """Create a SK chat completion service from agent config."""
    resolved_api_key = resolve_env_vars(config.api_key)
    resolved_base_url = resolve_env_vars(config.base_url)

    if config.service_type == ServiceType.AZURE_OPENAI:
        return AzureChatCompletion(
            deployment_name=config.model,
            endpoint=resolve_env_vars(config.endpoint),
            api_key=resolved_api_key,
            api_version=config.api_version or "2024-12-01-preview",
        )

    per_request_timeout = config.request_timeout

    if config.service_type == ServiceType.OPENAI_SSE_PROXY:
        if not resolved_base_url:
            raise ValueError("openai_sse_proxy requires base_url")
        async_client = SSEProxyAsyncOpenAI(
            api_key=resolved_api_key or "",
            base_url=resolved_base_url,
            timeout=per_request_timeout,
        )
        return OpenAIChatCompletion(
            ai_model_id=config.model,
            async_client=async_client,
        )

    # OpenAI or OpenAI-compatible endpoint
    # Key: OpenAIChatCompletion doesn't accept base_url directly.
    # Must pass via async_client=AsyncOpenAI(base_url=...)
    from openai import AsyncOpenAI

    if resolved_base_url:
        async_client = AsyncOpenAI(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            timeout=per_request_timeout,
        )
        return OpenAIChatCompletion(
            ai_model_id=config.model,
            async_client=async_client,
        )

    async_client = AsyncOpenAI(
        api_key=resolved_api_key,
        timeout=per_request_timeout,
    )
    return OpenAIChatCompletion(
        ai_model_id=config.model,
        async_client=async_client,
    )


def create_agent(config: AgentConfig) -> ChatCompletionAgent:
    """Create a ChatCompletionAgent from agent config."""
    service = create_service(config)
    return ChatCompletionAgent(
        name=config.name,
        description=config.description,
        instructions=config.instructions,
        service=service,
    )


def create_agent_with_scope(config: AgentConfig) -> ChatCompletionAgent:
    """Create a discussion agent with the shared scope constraint appended."""
    instructions = config.instructions
    if SCOPE_CONSTRAINT.strip() not in instructions:
        instructions = f"{instructions.rstrip()}\n\n{SCOPE_CONSTRAINT.strip()}"
    scoped_config = config.model_copy(update={"instructions": instructions})
    return create_agent(scoped_config)
