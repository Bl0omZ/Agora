from __future__ import annotations

import json
import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .blueprint import AgentSystemBlueprint


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
        files = [
            ExportFile(
                filename=f"{_sanitize_filename(agent.name)}.md",
                content=(
                    f"# {agent.name}\n\n"
                    f"Role: {agent.role}\n\n"
                    f"Goal: {agent.goal}\n\n"
                    "## Instructions\n\n"
                    f"{agent.instructions or 'Follow the blueprint workflow and produce the expected output.'}\n"
                ),
                mime_type="text/markdown",
            )
            for agent in blueprint.agents
        ]
        return ExportResult(format="prompt_pack", files=files)
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
