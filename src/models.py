"""Pydantic data models for agent-discussion CLI tool."""

from enum import Enum

from pydantic import BaseModel, Field


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
    prompt: str = (
        "Based on the discussion above, cast your vote.\n"
        "Respond with a JSON object: {\"agent_name\": \"YourName\", \"stance\": \"赞成/反对/中立\", "
        "\"reason\": \"your reasoning\", \"confidence\": 0.0-1.0}"
    )


class BrainstormConfig(BaseModel):
    """Configuration for the moderator brainstorm (topic refinement) phase."""

    enabled: bool = True
    max_rounds: int = Field(5, description="主持人最多问几轮（兜底，配合用户跳过按钮）")
    answer_timeout_seconds: int = Field(300, description="用户回答超时时间（秒），超时按 skip 处理")
    system_prompt: str = (
        "You are a discussion moderator. Before the panel discussion starts, "
        "your job is to refine the user's topic into a precise, well-scoped question.\n"
        "Ask ONE clarifying question at a time. Output JSON: "
        '{"action": "ask" | "finalize", '
        '"question": "...", '
        '"options": [{"id": "short_id", "label": "choice"}], '
        '"allow_multiple": false, '
        '"allow_freeform": true, '
        '"refined_topic": "..." (only when action=finalize), '
        '"context_summary": "..." (only when action=finalize), '
        '"complexity": {"level": "low|medium|high", "rationale": "...", "dimensions": ["..."]} (only when action=finalize), '
        '"dispatch_plan": {"execution_mode": "direct|focused|panel", "tasks": [{"agent_name": "AgentName", "sub_topic": "...", "expected_output": "..."}], "expected_final_output": "...", "rationale": "..."} (only when action=finalize)}'
    )

class AppConfig(BaseModel):
    """Top-level application configuration."""

    agents: list[AgentConfig]
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
