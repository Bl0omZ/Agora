"""Safe read/write helpers for the editable agents.yaml configuration."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import (
    AgentConfigPublic,
    AppConfig,
    AppConfigPublic,
    ConfigPayload,
    ModelProfile,
    ModelProfilePublic,
    PresetAgentPublic,
    PresetConfig,
    PresetConfigPublic,
    RuntimeParams,
)

SECRET_EXCLUDE_FIELDS = {"api_key", "secret", "token"}
ENV_TEMPLATE_RE = re.compile(r"^\$\{(\w+)(?::-[^}]*)?}$")


class ConfigWriteError(ValueError):
    """Raised when a config update fails validation or concurrency checks."""

    def __init__(self, detail: str, *, status_code: int = 422, field: str | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.field = field


def read_yaml_bytes(path: Path) -> bytes:
    """Read raw YAML bytes for hashing/export."""
    return path.read_bytes()


def compute_etag(yaml_bytes: bytes) -> str:
    """Return the short config ETag used by the REST API."""
    return hashlib.sha256(yaml_bytes).hexdigest()[:16]


def read_raw_config(path: Path) -> dict[str, Any]:
    """Read a YAML mapping from disk."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigWriteError("config root must be a mapping")
    return raw


def _bare_env_name(value: str | None) -> str:
    if not value:
        return ""
    match = ENV_TEMPLATE_RE.match(value.strip())
    if match:
        return match.group(1)
    return value.strip()


def _public_models(config: AppConfig) -> list[ModelProfilePublic]:
    return [ModelProfilePublic.model_validate(profile.model_dump()) for profile in config.models]


def _public_agents(config: AppConfig) -> list[AgentConfigPublic]:
    return [
        AgentConfigPublic(
            name=agent.name,
            description=agent.description,
            model=agent.model,
            is_moderator=index == config.manager_service_index,
            final_only=agent.final_only,
        )
        for index, agent in enumerate(config.agents)
    ]


def _public_presets(config: AppConfig) -> list[PresetConfigPublic]:
    agent_map = {agent.name: agent for agent in config.agents}
    presets: list[PresetConfigPublic] = []
    for name, preset in config.presets.items():
        presets.append(PresetConfigPublic(
            name=name,
            label=preset.label,
            description=preset.description,
            agents=[
                PresetAgentPublic(
                    name=agent_name,
                    description=agent_map[agent_name].description,
                    model=agent_map[agent_name].model,
                )
                for agent_name in preset.agents
                if agent_name in agent_map
            ],
        ))
    return presets


def to_public_config(config: AppConfig) -> AppConfigPublic:
    """Convert an internal config into the explicit public frontend contract."""
    return AppConfigPublic(
        models=_public_models(config),
        agents=_public_agents(config),
        presets=_public_presets(config),
        runtime=RuntimeParams(
            max_rounds=config.discussion.max_rounds or 0,
            brainstorm_enabled=config.brainstorm.enabled,
            voting_timeout_s=config.voting.per_agent_timeout_s,
            summary_model=config.summary_model,
        ),
    )


def _validate_raw(raw: dict[str, Any]) -> ConfigPayload:
    try:
        return ConfigPayload.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(item) for item in first.get("loc", ()))
        message = first.get("msg", str(exc))
        raise ConfigWriteError(message, field=loc or None) from exc
    except ValueError as exc:
        raise ConfigWriteError(str(exc)) from exc


def write_raw_config_atomic(path: Path, raw: dict[str, Any]) -> str:
    """Validate and atomically replace the YAML config, returning the new ETag."""
    _validate_raw(raw)
    text = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, indent=2)
    directory = path.parent
    fd = -1
    tmp_name = ""
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(text)
        # Re-validate the exact serialized file before it becomes authoritative.
        serialized_raw = yaml.safe_load(Path(tmp_name).read_text(encoding="utf-8")) or {}
        _validate_raw(serialized_raw)
        os.replace(tmp_name, path)
    except Exception:
        if fd != -1:
            os.close(fd)
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        raise
    return compute_etag(read_yaml_bytes(path))


def assert_etag_matches(path: Path, if_match: str | None) -> None:
    """Validate optimistic concurrency precondition."""
    current = compute_etag(read_yaml_bytes(path))
    if if_match != current:
        raise ConfigWriteError("config_modified_elsewhere", status_code=409)


def update_models(raw: dict[str, Any], payload: Any) -> dict[str, Any]:
    data = payload.get("models", payload) if isinstance(payload, dict) else payload
    profiles = [ModelProfile.model_validate(item) for item in data]
    updated = dict(raw)
    updated["models"] = [profile.model_dump() for profile in profiles]
    return updated


def update_presets(raw: dict[str, Any], payload: Any) -> dict[str, Any]:
    data = payload.get("presets", payload) if isinstance(payload, dict) else payload
    updated_presets: dict[str, Any] = {}
    for item in data:
        name = item["name"]
        preset = PresetConfig(
            label=item["label"],
            description=item["description"],
            agents=[
                agent["name"] if isinstance(agent, dict) else str(agent)
                for agent in item.get("agents", [])
            ],
        )
        updated_presets[name] = preset.model_dump()
    updated = dict(raw)
    updated["presets"] = updated_presets
    return updated


def update_runtime(raw: dict[str, Any], payload: Any) -> dict[str, Any]:
    data = payload.get("runtime", payload) if isinstance(payload, dict) else payload
    runtime = RuntimeParams.model_validate(data)
    updated = dict(raw)
    discussion = dict(updated.get("discussion") or {})
    discussion["max_rounds"] = runtime.max_rounds
    updated["discussion"] = discussion
    brainstorm = dict(updated.get("brainstorm") or {})
    brainstorm["enabled"] = runtime.brainstorm_enabled
    updated["brainstorm"] = brainstorm
    voting = dict(updated.get("voting") or {})
    voting["per_agent_timeout_s"] = runtime.voting_timeout_s
    updated["voting"] = voting
    updated["summary_model"] = runtime.summary_model
    return updated


def update_agents(raw: dict[str, Any], payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = payload.get("agents", payload) if isinstance(payload, dict) else payload
    drafts = [AgentConfigPublic.model_validate(item) for item in data]
    registry_names = {
        profile["name"] if isinstance(profile, dict) else profile.name
        for profile in raw.get("models", []) or []
    }
    existing_agents = {
        str(agent.get("name")): dict(agent)
        for agent in raw.get("agents", []) or []
        if isinstance(agent, dict) and agent.get("name")
    }
    sanitized: list[dict[str, Any]] = []
    updated_agents: list[dict[str, Any]] = []
    manager_service_index = 0
    for index, draft in enumerate(drafts):
        agent = existing_agents.get(draft.name, {"name": draft.name, "instructions": ""})
        agent.update({
            "name": draft.name,
            "description": draft.description,
            "model": draft.model,
            "final_only": draft.final_only,
        })
        if draft.model in registry_names:
            fields: list[str] = []
            for field in ("base_url", "api_key"):
                if field in agent:
                    agent.pop(field, None)
                    fields.append(field)
            if fields:
                sanitized.append({"agent_name": draft.name, "sanitized_fields": fields})
        if draft.is_moderator:
            manager_service_index = index
        updated_agents.append(agent)
    updated = dict(raw)
    updated["agents"] = updated_agents
    updated["manager_service_index"] = manager_service_index
    return updated, sanitized
