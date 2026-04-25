"""Markdown report generation for agent-discussion."""

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
) -> str:
    """Build the markdown report content."""
    lines = [
        "# 讨论报告",
        "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"- 讨论话题：{topic}",
        "",
        "## 最终方案",
        "",
        discussion_summary or "（无）",
        "",
    ]

    if dispatch_state:
        selected_agents = ", ".join(dispatch_state.get("selected_agents") or []) or "无"
        complexity = dispatch_state.get("complexity") or {}
        lines.extend(
            [
                "## 执行计划",
                "",
                f"- 原始议题：{dispatch_state.get('original_topic') or topic}",
                f"- 精炼议题：{dispatch_state.get('refined_topic') or topic}",
                f"- 复杂度：{complexity.get('level') or 'medium'}",
                f"- 执行模式：{dispatch_state.get('execution_mode') or 'panel'}",
                f"- 派发 agent：{selected_agents}",
                f"- 最终产出：{dispatch_state.get('expected_final_output') or '（未指定）'}",
                "",
            ]
        )

    if voting_result is not None:
        lines.extend(
            [
                "## 方案评审",
                "",
                f"- 结论：{voting_result.conclusion}",
                "",
                "| Agent | 立场 | 原因 | 置信度 |",
                "|---|---|---|---|",
            ]
        )
        for vote in voting_result.votes:
            reason = vote.reason.replace("\n", " ").strip()
            lines.append(f"| {vote.agent_name} | {vote.stance} | {reason} | {vote.confidence:.1f} |")
        lines.append("")

    lines.extend(
        [
            "## 完整讨论记录",
            "",
            "```text",
            discussion_transcript or "（无）",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _slugify(topic: str) -> str:
    """Create a filesystem-friendly file stem."""
    normalized = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", topic.strip(), flags=re.UNICODE)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return (normalized or "discussion-report")[:80]
