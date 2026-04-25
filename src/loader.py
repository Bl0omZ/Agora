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
    """Resolve ${ENV_VAR} references in a string."""
    if value is None:
        return None
    pattern = r"\$\{(\w+)\}"

    def replacer(match: re.Match) -> str:
        env_key = match.group(1)
        env_val = os.environ.get(env_key)
        if env_val is None:
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

    # Validate environment variables are available
    for agent in config.agents:
        resolve_env_vars(agent.api_key)
        resolve_env_vars(agent.base_url)
        resolve_env_vars(agent.endpoint)

    return config


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

    if config.service_type == ServiceType.OPENAI_SSE_PROXY:
        if not resolved_base_url:
            raise ValueError("openai_sse_proxy requires base_url")
        async_client = SSEProxyAsyncOpenAI(
            api_key=resolved_api_key or "",
            base_url=resolved_base_url,
        )
        return OpenAIChatCompletion(
            ai_model_id=config.model,
            async_client=async_client,
        )

    # OpenAI or OpenAI-compatible endpoint
    # Key: OpenAIChatCompletion doesn't accept base_url directly.
    # Must pass via async_client=AsyncOpenAI(base_url=...)
    if resolved_base_url:
        from openai import AsyncOpenAI

        async_client = AsyncOpenAI(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
        )
        return OpenAIChatCompletion(
            ai_model_id=config.model,
            async_client=async_client,
        )

    return OpenAIChatCompletion(
        ai_model_id=config.model,
        api_key=resolved_api_key,
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
