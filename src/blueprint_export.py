from __future__ import annotations

import json
import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .blueprint import AgentSystemBlueprint, BlueprintAgentSpec


def _sanitize_filename(name: str) -> str:
    """Remove characters unsafe for filenames, including markdown link syntax."""
    name = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", name)
    name = re.sub(r"[/\\:*?\"<>|]", "_", name)
    return name.strip() or "blueprint"


ExportFormat = Literal["markdown", "json", "yaml", "prompt_pack"]


class ExportFile(BaseModel):
    filename: str
    content: str
    mime_type: str


class ExportResult(BaseModel):
    format: ExportFormat
    files: list[ExportFile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unsupported_fields: list[str] = Field(default_factory=list)


def export_blueprint(blueprint: AgentSystemBlueprint, export_format: ExportFormat) -> ExportResult:
    if export_format == "json":
        return ExportResult(
            format="json",
            files=[
                ExportFile(
                    filename=f"{_sanitize_filename(blueprint.id)}.json",
                    content=json.dumps(blueprint.model_dump(mode="json"), ensure_ascii=False, indent=2),
                    mime_type="application/json",
                )
            ],
        )
    if export_format == "yaml":
        return ExportResult(
            format="yaml",
            files=[
                ExportFile(
                    filename=f"{_sanitize_filename(blueprint.id)}.yaml",
                    content=yaml.safe_dump(
                        blueprint.model_dump(mode="json"),
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    mime_type="application/yaml",
                )
            ],
        )
    if export_format == "prompt_pack":
        files: list[ExportFile] = []
        unsupported_fields: list[str] = []
        warnings: list[str] = []
        for agent in blueprint.agents:
            content, unsupported = _to_prompt_pack_content(agent)
            if unsupported:
                unsupported_fields.append(f"agents[{agent.name}].instructions")
                warnings.append(
                    f"{agent.name} 的 instructions 过短或与 goal 重复，已补充 outputs/collaboration_rules。"
                )
            files.append(
                ExportFile(
                    filename=f"{_sanitize_filename(agent.name)}.md",
                    content=content,
                    mime_type="text/markdown",
                )
            )
        return ExportResult(
            format="prompt_pack",
            files=files,
            warnings=warnings,
            unsupported_fields=unsupported_fields,
        )
    return ExportResult(
        format="markdown",
        files=[
            ExportFile(
                filename=f"{_sanitize_filename(blueprint.id)}.md",
                content=_to_markdown(blueprint),
                mime_type="text/markdown",
            )
        ],
    )


def _to_prompt_pack_content(agent: BlueprintAgentSpec) -> tuple[str, bool]:
    instructions = (agent.instructions or "").strip()
    goal = (agent.goal or "").strip()
    unsupported = not instructions or instructions == goal or len(instructions) < 50
    if unsupported:
        instructions = (
            "Follow the blueprint workflow. Use the role, goal, expected outputs, "
            "and collaboration rules below as the operational instruction set."
        )

    lines = [
        f"# {agent.name}",
        "",
        f"Role: {agent.role}",
        "",
        f"Goal: {agent.goal}",
        "",
        "## Instructions",
        "",
        instructions,
    ]
    if agent.outputs:
        lines.extend(["", "## Expected Outputs", ""])
        lines.extend(f"- {output}" for output in agent.outputs)
    if agent.collaboration_rules:
        lines.extend(["", "## Collaboration Rules", ""])
        lines.extend(f"- {rule}" for rule in agent.collaboration_rules)
    return "\n".join(lines).strip() + "\n", unsupported


def _to_markdown(blueprint: AgentSystemBlueprint) -> str:
    lines = [
        f"# {blueprint.name}",
        "",
        "## Problem",
        "",
        blueprint.problem_statement,
        "",
        "## Agents",
        "",
    ]
    for agent in blueprint.agents:
        lines.extend([f"### {agent.name}", "", f"- Role: {agent.role}", f"- Goal: {agent.goal}", ""])
    lines.extend(["## Workflow", ""])
    for step in blueprint.workflow.steps:
        lines.append(f"- {step.id}: {step.name} -> {step.output}")
    lines.extend(["", "## Evaluation", ""])
    for criterion in blueprint.evaluation.criteria:
        lines.append(f"- {criterion}")
    if blueprint.generation.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in blueprint.generation.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines).strip() + "\n"
