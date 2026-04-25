"""Voting module with per-agent timeout isolation."""

import asyncio
import logging
import re

from pydantic import BaseModel

from semantic_kernel.agents import Agent
from semantic_kernel.contents import AuthorRole, ChatMessageContent

logger = logging.getLogger(__name__)


class VoteResult(BaseModel):
    """A single agent's vote."""

    agent_name: str
    stance: str = "中立"  # 赞成 / 反对 / 中立
    reason: str
    confidence: float = 0.5


class VotingSummary(BaseModel):
    """Aggregated voting result."""

    votes: list[VoteResult]
    conclusion: str


async def run_voting(
    agents: list[Agent],
    topic: str,
    discussion_context: str,
    voting_prompt: str,
    per_agent_timeout: float = 120,
) -> VotingSummary:
    """Run parallel voting with per-agent timeout isolation."""
    task = (
        f"Topic: {topic}\n\nFinal proposal to review:\n{discussion_context}\n\n{voting_prompt}\n\n"
        "You are reviewing the final proposal, not producing the final answer. "
        "Do NOT include <think> blocks or hidden chain-of-thought in any field. "
        "The reason field must contain only the final user-visible rationale."
    )
    votes = await asyncio.gather(*[
        _collect_vote(agent, task, per_agent_timeout) for agent in agents
    ])

    return VotingSummary(
        votes=votes,
        conclusion=_summarize_conclusion(votes),
    )


async def _collect_vote(agent: Agent, task: str, timeout_seconds: float) -> VoteResult:
    """Collect one vote without letting a single slow agent block the whole round."""
    try:
        response = await asyncio.wait_for(
            agent.get_response(
                messages=[ChatMessageContent(role=AuthorRole.USER, content=task)],
            ),
            timeout=timeout_seconds,
        )
        vote = _parse_vote(response.message)
        return vote.model_copy(update={"agent_name": getattr(agent, "name", "Unknown")})
    except TimeoutError:
        logger.warning("Voting timed out for agent %s after %ss", getattr(agent, "name", "Unknown"), timeout_seconds)
        return VoteResult(
            agent_name=getattr(agent, "name", "Unknown"),
            stance="中立",
            reason=f"超时（{timeout_seconds:.0f}s）",
            confidence=0.0,
        )
    except Exception as ex:
        logger.warning("Voting failed for agent %s: %s", getattr(agent, "name", "Unknown"), ex)
        return VoteResult(
            agent_name=getattr(agent, "name", "Unknown"),
            stance="中立",
            reason=f"{type(ex).__name__}: {str(ex)[:240]}",
            confidence=0.0,
        )


def _summarize_conclusion(votes: list[VoteResult]) -> str:
    """Create a simple deterministic conclusion from collected votes."""
    support_count = sum(1 for vote in votes if vote.stance == "赞成")
    oppose_count = sum(1 for vote in votes if vote.stance == "反对")
    neutral_count = len(votes) - support_count - oppose_count

    if support_count > oppose_count:
        return f"多数赞成（{support_count} 赞成 / {oppose_count} 反对 / {neutral_count} 中立）"
    if oppose_count > support_count:
        return f"多数反对（{support_count} 赞成 / {oppose_count} 反对 / {neutral_count} 中立）"
    return f"无明确多数（{support_count} 赞成 / {oppose_count} 反对 / {neutral_count} 中立）"


def _parse_vote(msg: ChatMessageContent) -> VoteResult:
    """Parse a single agent response into a VoteResult."""
    content = msg.content or ""

    # Try direct JSON parse
    try:
        return _sanitize_vote(VoteResult.model_validate_json(content))
    except Exception:
        pass

    # Try extracting JSON block
    match = re.search(r"\{[^}]*\}", content, re.DOTALL)
    if match:
        try:
            return _sanitize_vote(VoteResult.model_validate_json(match.group()))
        except Exception:
            pass

    # Fallback: extract what we can
    stance = "中立"
    if re.search(r"support|赞同|支持", content, re.IGNORECASE):
        stance = "赞成"
    elif re.search(r"oppose|反对", content, re.IGNORECASE):
        stance = "反对"

    return VoteResult(
        agent_name=msg.name or "Unknown",
        stance=stance,
        reason=_strip_think_blocks(content)[:300],
        confidence=0.3,
    )


def _sanitize_vote(vote: VoteResult) -> VoteResult:
    """Remove provider scratchpad tags from the user-visible vote reason."""
    return vote.model_copy(update={"reason": _strip_think_blocks(vote.reason).strip()})


def _strip_think_blocks(text: str) -> str:
    """Strip XML-style reasoning blocks sometimes emitted by local models."""
    return re.sub(r"<think\b[^>]*>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
