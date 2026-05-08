"""Pydantic data models for Agora CLI tool."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ServiceType(str, Enum):
    """Supported AI service providers."""

    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENAI_SSE_PROXY = "openai_sse_proxy"


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    name: str
    description: str = Field(..., description="Agent description. Required by GroupChatOrchestration.")
    instructions: str
    service_type: ServiceType = ServiceType.OPENAI
    model: str = Field(..., description="Model ID (e.g. gpt-4o, claude-sonnet-4-20250514)")
    api_key: str | None = Field(None, description="API key. Supports ${ENV_VAR} syntax.")
    base_url: str | None = Field(None, description="Custom API endpoint URL. Supports ${ENV_VAR} syntax.")
    endpoint: str | None = Field(None, description="Azure OpenAI endpoint. Supports ${ENV_VAR} syntax.")
    api_version: str | None = Field("2024-12-01-preview", description="Azure OpenAI API version.")
    final_only: bool = Field(False, description="If true, this agent only speaks at the end (e.g. synthesizer).")
    request_timeout: float = Field(240.0, description="Per-request timeout in seconds for this agent's LLM calls.")


class ModelProfile(BaseModel):
    """Reusable model registry entry.

    ``env_var_name`` stores the bare environment variable name (for example
    ``MIMO_API_KEY``), never the resolved secret value.
    """

    name: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    env_var_name: str | None = None
    models: list[str] = Field(..., min_length=1)
    key: str | None = Field(None, exclude=True)

    @field_validator("models", mode="before")
    @classmethod
    def _normalize_models(cls, value):
        if not isinstance(value, list):
            return value
        return [item.get("id") if isinstance(item, dict) else item for item in value]

    @model_validator(mode="after")
    def _default_env_var_name(self) -> "ModelProfile":
        if not self.env_var_name:
            self.env_var_name = f"{self.name.upper()}_API_KEY"
        return self


class ModelProfilePublic(BaseModel):
    """Public model registry view; intentionally excludes secrets."""

    name: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    base_url: str = Field(default="")
    env_var_name: str = Field(..., min_length=1)
    models: list[str] = Field(..., min_length=1)
    key_masked: str | None = None


class AgentConfigPublic(BaseModel):
    """Public agent view; intentionally excludes api_key/base_url/model_id."""

    name: str
    description: str
    model: str
    is_moderator: bool = False
    final_only: bool = False


class PresetConfig(BaseModel):
    """A named combination of discussion agents."""

    label: str = Field(..., description="Display label for this preset.")
    description: str = Field(..., description="Short explanation of the preset focus.")
    agents: list[str] = Field(..., description="Discussion agent names included in this preset.")


class PresetAgentPublic(BaseModel):
    """Public preset member view."""

    name: str
    description: str
    model: str | None = None


class PresetConfigPublic(BaseModel):
    """Public preset view."""

    name: str
    label: str
    description: str
    agents: list[PresetAgentPublic]


class DiscussionConfig(BaseModel):
    """Configuration for the discussion phase."""

    enabled: bool = True
    max_rounds: int | None = Field(10, description="Maximum discussion rounds. None for unlimited.")
    selection_prompt: str = (
        "You are a discussion moderator. Select the next speaker based on the conversation.\n"
        "Participants: {{$participants}}\n"
        "Respond with only a JSON object: {\"result\": \"AgentName\", \"reason\": \"...\"}"
    )
    termination_prompt: str = (
        "You are a discussion moderator. Determine if the discussion has reached a conclusion.\n"
        "Respond with only a JSON object: {\"result\": true/false, \"reason\": \"...\"}"
    )
    result_filter_prompt: str = (
        "You are a discussion moderator. The discussion has concluded.\n"
        "Summarize the key points and conclusion.\n"
        "Respond with only a JSON object: {\"result\": \"summary text\", \"reason\": \"...\"}"
    )


class VotingConfig(BaseModel):
    """Configuration for the voting phase."""

    enabled: bool = True
    per_agent_timeout_s: float = Field(120, description="Per-agent voting timeout in seconds.")
    prompt: str = (
        "Based on the discussion above, cast your vote.\n"
        "Respond with a JSON object: {\"agent_name\": \"YourName\", \"stance\": \"赞成/反对/中立\", "
        "\"reason\": \"your reasoning\", \"confidence\": 0.0-1.0}"
    )


class BrainstormConfig(BaseModel):
    """Configuration for the moderator brainstorm (topic refinement) phase."""

    enabled: bool = True
    max_rounds: int = Field(10, description="主持人最多问几轮（兜底，配合用户跳过按钮）")
    answer_timeout_seconds: int = Field(300, description="用户回答超时时间（秒），超时按 skip 处理")
    system_prompt: str = (
        "You are a moderator running a lightweight requirements interview before a multi-agent discussion.\n"
        "Your goal is to turn the user's raw topic into an execution-ready discussion brief. "
        "Do not rush to finalize. First collect enough context so later agents can give specific, "
        "grounded advice instead of generic suggestions.\n\n"
        "Ask ONE question at a time.\n\n"
        "Question strategy:\n"
        "1. Start with the weakest missing dimension.\n"
        "2. Prefer concrete, answerable questions.\n"
        "3. Prefer multiple-choice options when useful, but allow freeform answers.\n"
        "4. If the user gives a vague answer, ask for a number, example, constraint, tradeoff, or failure case.\n"
        "5. Do not ask for information already present in the conversation.\n"
        "6. Do not overfit to one domain. Infer the domain from the user's topic, but keep the clarification framework generic.\n\n"
        "Clarify these dimensions before action=finalize when relevant:\n"
        "- Current state: what already exists, what process/tool/system is currently used.\n"
        "- Desired outcome: what the user wants to decide, produce, or improve.\n"
        "- Pain point: what is failing, too slow, too noisy, too expensive, or unclear.\n"
        "- Scale: volume, frequency, backlog, latency, cost, team size, or other concrete magnitude.\n"
        "- Evidence gap: what information is missing to judge correctness, risk, quality, or feasibility.\n"
        "- Constraints: technical, organizational, time, cost, permission, or integration limits.\n"
        "- Non-goals: what should stay out of scope for the first discussion.\n"
        "- Decision boundaries: what the agents may decide, and what must remain for the user.\n"
        "- Success criteria: how the user will judge that the final answer is useful.\n\n"
        "Finalize only when the discussion brief contains the current situation, the main pain point, "
        "at least one concrete scale or example when available, key constraints or non-goals, "
        "and the expected final output shape.\n\n"
        "When more clarification is needed, output JSON only: "
        '{"action": "ask", '
        '"question": "...", '
        '"options": [{"id": "short_id", "label": "choice"}], '
        '"allow_multiple": false, '
        '"allow_freeform": true}\n\n'
        "When finalizing, output JSON only: "
        '{"action": "finalize", '
        '"refined_topic": "...", '
        '"context_summary": "...", '
        '"complexity": {"level": "low|medium|high", "rationale": "...", "dimensions": ["..."]}, '
        '"dispatch_plan": {"execution_mode": "direct|focused|panel", "tasks": [{"agent_name": "AgentName", "sub_topic": "...", "expected_output": "..."}], "expected_final_output": "...", "rationale": "..."}}'
    )


class RuntimeParams(BaseModel):
    """Aggregated runtime settings exposed to the frontend."""

    max_rounds: int
    brainstorm_enabled: bool
    voting_timeout_s: float
    summary_model: str | None = None


class KeyPoint(BaseModel):
    """A single extracted argument from one participant."""

    agent_name: str
    text: str


class AgentParticipant(BaseModel):
    """Participant summary for the discussion dashboard."""

    name: str
    role: str
    model: str
    is_moderator: bool
    message_count: int
    key_points: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_keypoint_objects(cls, data):
        """Accept legacy KeyPoint objects while serializing as string chips."""
        if not isinstance(data, dict):
            return data
        key_points = data.get("key_points")
        if isinstance(key_points, list):
            data = dict(data)
            data["key_points"] = [
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in key_points
            ]
        return data


class DiscussionSummary(BaseModel):
    """Structured synthesis payload sent as the discussion_summary WS event."""

    schema_version: int = 2
    participants: list[AgentParticipant]
    distilled_conclusion: str
    degraded: bool = False
    degraded_reason: Literal["json_parse_failed", "synthesis_truncated"] | None = None


class AppConfigPublic(BaseModel):
    """Public config payload; intentionally excludes all secret-bearing fields."""

    models: list[ModelProfilePublic] = Field(default_factory=list)
    agents: list[AgentConfigPublic]
    presets: list[PresetConfigPublic] = Field(default_factory=list)
    runtime: RuntimeParams


class ConfigPayload(BaseModel):
    """Writable config payload used for schema validation before atomic replace."""

    models: list[ModelProfile] = Field(default_factory=list)
    agents: list[AgentConfig]
    presets: dict[str, PresetConfig] = Field(default_factory=dict)
    default_preset: str | None = None
    discussion: DiscussionConfig = DiscussionConfig()
    voting: VotingConfig = VotingConfig()
    brainstorm: BrainstormConfig = BrainstormConfig()
    manager_service_index: int = 0
    supports_structured_output: bool = True
    summary_model: str | None = None

    @model_validator(mode="after")
    def _validate_summary_model(self) -> "ConfigPayload":
        if self.summary_model is None:
            return self
        if "/" not in self.summary_model:
            raise ValueError("summary_model must use provider/model_id format")
        provider_name, model_id = self.summary_model.split("/", 1)
        registry = {profile.name: profile for profile in self.models}
        if provider_name not in registry or model_id not in registry[provider_name].models:
            raise ValueError("summary_model must reference a model registry model")
        return self


class AppConfig(BaseModel):
    """Top-level application configuration."""

    models: list[ModelProfile] = Field(default_factory=list)
    agents: list[AgentConfig]
    presets: dict[str, PresetConfig] = Field(default_factory=dict)
    default_preset: str | None = None
    discussion: DiscussionConfig = DiscussionConfig()
    voting: VotingConfig = VotingConfig()
    brainstorm: BrainstormConfig = BrainstormConfig()
    manager_service_index: int = Field(
        0, description="Index of the agent whose service drives the GroupChatManager."
    )
    supports_structured_output: bool = Field(
        True,
        description="Whether endpoints support structured output. Set false to fallback to prompt+regex.",
    )
    summary_model: str | None = None

    @model_validator(mode="after")
    def _validate_summary_model(self) -> "AppConfig":
        if self.summary_model is None:
            return self
        if "/" not in self.summary_model:
            raise ValueError("summary_model must use provider/model_id format")
        provider_name, model_id = self.summary_model.split("/", 1)
        registry = {profile.name: profile for profile in self.models}
        if provider_name not in registry or model_id not in registry[provider_name].models:
            raise ValueError("summary_model must reference a model registry model")
        return self
