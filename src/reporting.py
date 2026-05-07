"""Markdown report generation for Agora."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from pathlib import Path
from .voting import VotingSummary


def get_default_report_dir() -> Path:
    """Return the default report directory under the package root."""
    return Path(__file__).resolve().parents[1] / "report"


def save_report(
    *,
    topic: str,
    discussion_summary: str,
    discussion_transcript: str,
    voting_result: VotingSummary | None = None,
    dispatch_state: dict[str, Any] | None = None,
    blueprint: Any | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Persist a markdown report and return its path."""
    report_dir = output_dir or get_default_report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"{datetime.now():%Y-%m-%d}-{_slugify(topic)}.md"
    report_path.write_text(
        _build_report_markdown(
            topic=topic,
            discussion_summary=discussion_summary,
            discussion_transcript=discussion_transcript,
            voting_result=voting_result,
            dispatch_state=dispatch_state,
            blueprint=blueprint,
        ),
        encoding="utf-8",
    )
    return report_path


def _build_report_markdown(
    *,
    topic: str,
    discussion_summary: str,
    discussion_transcript: str,
    voting_result: VotingSummary | None,
    dispatch_state: dict[str, Any] | None = None,
    blueprint: Any | None = None,
) -> str:
    """Build the markdown report content with professional structure.

    Follows technical-writer guidelines: clear structure, actionable conclusions,
    precise language. Avoids AI writing patterns: no 综上所述, 值得注意的是,
    我们可以看到, or empty modifiers like 显著/充分/有效.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# {topic}",
        "",
        f"> 生成时间：{now_str}",
        "",
        "## 概述",
        "",
        _extract_key_finding(discussion_summary),
        "",
    ]

    if dispatch_state:
        selected_agents = dispatch_state.get("selected_agents") or []
        complexity = dispatch_state.get("complexity") or {}
        refined_topic = dispatch_state.get("refined_topic") or topic
        lines.extend(
            [
                "## 讨论设置",
                "",
                f"- 原始议题：{dispatch_state.get('original_topic') or topic}",
                f"- 精炼议题：{refined_topic}",
                f"- 复杂度：{complexity.get('level') or 'medium'}",
                f"- 执行模式：{dispatch_state.get('execution_mode') or 'panel'}",
                f"- 参与 agent：{', '.join(selected_agents) if selected_agents else '无'}",
                f"- 目标产出：{dispatch_state.get('expected_final_output') or '（未指定）'}",
                "",
            ]
        )

    lines.extend(
        [
            "## 方案详情",
            "",
            discussion_summary or "（本轮未产出方案）",
            "",
        ]
    )

    if voting_result is not None:
        lines.extend(
            [
                "## 评审结论",
                "",
                voting_result.conclusion,
                "",
                "| Agent | 立场 | 理由 | 置信度 |",
                "|---|---|---|---|",
            ]
        )
        for vote in voting_result.votes:
            reason = vote.reason.replace("\n", " ").strip()
            lines.append(f"| {vote.agent_name} | {vote.stance} | {reason} | {vote.confidence:.1f} |")
        lines.append("")

    if blueprint is not None:
        lines.extend(_build_blueprint_markdown(blueprint))

    lines.extend(
        [
            "## 讨论过程",
            "",
            "```text",
            discussion_transcript or "（无）",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _extract_key_finding(summary: str) -> str:
    """Extract the first substantive paragraph as the overview.

    Walks through lines, skipping markdown headers, metadata lines
    (lines dominated by **bold markers**), and blank lines, until it
    finds a natural-language paragraph of at least 20 characters.
    """
    for line in (summary or "").split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        # Skip lines that are mostly bold markup (e.g. "**核心立场差异**")
        bold_chars = stripped.count("**")
        text_chars = len(stripped.replace("**", "").strip())
        if bold_chars >= 2 and text_chars < 20:
            continue
        if len(stripped) >= 20:
            return stripped
    return summary.strip()[:200] or "本轮讨论未产出明确结论。"


def _blueprint_data(blueprint: Any) -> dict[str, Any]:
    model_dump = getattr(blueprint, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(blueprint, dict):
        return blueprint
    return {}


def _build_blueprint_markdown(blueprint: Any) -> list[str]:
    data = _blueprint_data(blueprint)
    lines = ["## 本次讨论总览", ""]

    problem = data.get("problem_statement")
    if problem:
        lines.extend(["### Problem", "", str(problem), ""])

    lines.extend(["### Agents", ""])
    for agent in data.get("agents") or []:
        name = agent.get("name") or "Agent"
        role = agent.get("role") or ""
        goal = agent.get("goal") or ""
        label = f"- {name}"
        details = " / ".join(part for part in [role, goal] if part)
        lines.append(f"{label}: {details}" if details else label)
    lines.append("")

    lines.extend(["### Workflow", ""])
    workflow = data.get("workflow") or {}
    for step in workflow.get("steps") or []:
        step_id = step.get("id") or "step"
        name = step.get("name") or ""
        output = step.get("output") or ""
        lines.append(f"- {step_id}: {name} -> {output}")
    lines.append("")

    lines.extend(["### Evaluation", ""])
    evaluation = data.get("evaluation") or {}
    for criterion in evaluation.get("criteria") or []:
        lines.append(f"- {criterion}")
    lines.append("")

    generation = data.get("generation") or {}
    warnings = generation.get("warnings") or []
    if warnings:
        lines.extend(["### Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return lines


def _slugify(topic: str) -> str:
    """Create a filesystem-friendly file stem."""
    normalized = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", topic.strip(), flags=re.UNICODE)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return (normalized or "discussion-report")[:30]
