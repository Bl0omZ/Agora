"""Brainstorm module: Moderator-driven topic refinement via multi-turn Q&A.

This module implements the optional `brainstorming` phase that runs *before*
the main panel discussion. A moderator LLM asks the user one clarifying
question at a time (with multiple-choice options + free-text fallback) to
refine the user's raw topic into a precise, well-scoped question that is
then handed off to the discussion agents.

Design reference:
    docs/plans/2026-04-24-moderator-brainstorm-design.md (sections 6.1, 8)

Acceptance criteria covered here:
    AC2.3 — at most ``config.max_rounds`` moderator turns, then forced finalize
    AC2.5 — refined_topic truncated to 300 chars with an ellipsis suffix
    AC3.2 — JSON parse failures retry once, then fall back to original_topic
    Implicitly supports AC3.1 by honoring SkipBrainstormException raised by
    the on_question callback (the websocket layer raises it on user-skip or
    answer timeout).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent
from semantic_kernel.kernel import Kernel

from .models import BrainstormConfig

logger = logging.getLogger(__name__)

# Maximum length of refined_topic per AC2.5.
_REFINED_TOPIC_MAX_CHARS = 300
# Number of extra parse attempts after the initial one (per AC3.2 — "retry 1 time").
_JSON_RETRY_ATTEMPTS = 1
_FINALIZE_SCHEMA_REMINDER = (
    "\n\nFinalize output is invalid unless it includes all of these fields: "
    "refined_topic, context_summary, complexity, dispatch_plan. "
    "complexity must be an object with level (low|medium|high), rationale, and dimensions. "
    "dispatch_plan must be an object with execution_mode (direct|focused|panel), "
    "tasks, expected_final_output, and rationale."
)


class SkipBrainstormException(Exception):
    """Raised by the ``on_question`` callback when the user opts out.

    The web layer raises this in two situations:
      * user explicitly clicks "skip / start discussion now"
      * user fails to respond within ``answer_timeout_seconds``

    ``BrainstormSession.run`` catches this and forces the LLM to finalize
    using whatever history has been accumulated so far. If no history
    exists yet, ``original_topic`` is returned verbatim as the refined
    topic.
    """


class BrainstormSession:
    """Multi-turn Q&A session driven by a moderator LLM.

    The session orchestrates a state machine with three terminal transitions:

    +-----------------+----------------------------------------------------+
    | Trigger         | Behavior                                           |
    +=================+====================================================+
    | LLM action=ask  | Append question to history, await user answer via  |
    |                 | ``on_question``, append answer, loop.              |
    +-----------------+----------------------------------------------------+
    | LLM action=     | Return refined_topic + context_summary (truncated  |
    | finalize        | per AC2.5).                                        |
    +-----------------+----------------------------------------------------+
    | round ==        | Re-prompt LLM with a "MUST finalize" suffix; if it |
    | max_rounds      | still asks, force a fallback finalize.             |
    +-----------------+----------------------------------------------------+
    | SkipBrainstorm  | Force finalize from current history; if history is |
    | Exception       | empty, return original_topic verbatim.             |
    +-----------------+----------------------------------------------------+
    | JSON parse fail | Retry once (``_JSON_RETRY_ATTEMPTS``); on second   |
    |                 | failure, finalize with original_topic (AC3.2).     |
    +-----------------+----------------------------------------------------+

    The ``history`` field uses a UI-friendly shape (``[{role, content}]``)
    rather than ``ChatHistory`` because it is forwarded to the frontend and
    persisted into ``SessionMeta.brainstorm_history``.
    """

    def __init__(
        self,
        config: BrainstormConfig,
        kernel: Kernel,
        service_id: str,
        on_question: Callable[[dict], Awaitable[str]],
    ) -> None:
        """Construct a brainstorm session.

        Args:
            config: BrainstormConfig controlling max_rounds, system_prompt, etc.
            kernel: Semantic Kernel instance used to look up the chat service.
            service_id: ID of the chat completion service that drives the
                moderator. Typically the same service backing the
                GroupChatManager (see ``AppConfig.manager_service_index``).
            on_question: Async callback invoked once per ``ask`` turn. Receives
                ``{question, options, allow_freetext, round, model}`` and must
                return the user's answer string. May raise
                ``SkipBrainstormException`` to abort the loop.
        """
        self.config = config
        self.kernel = kernel
        self.service_id = service_id
        self.on_question = on_question
        self.history: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, original_topic: str) -> dict:
        """Execute the brainstorm loop and return the refined topic.

        Args:
            original_topic: The raw topic string the user submitted.

        Returns:
            ``{"refined_topic": str, "context_summary": str, "history": list[dict]}``
            ``refined_topic`` is guaranteed to be ``≤ _REFINED_TOPIC_MAX_CHARS``
            characters. ``history`` is a list of ``{role, content}`` dicts where
            ``role`` is one of ``"user"`` or ``"moderator"``.
        """
        logger.info(
            "BrainstormSession.run start: topic=%r max_rounds=%d service_id=%s",
            original_topic,
            self.config.max_rounds,
            self.service_id,
        )

        service = self._resolve_service()
        round_idx = 0

        while round_idx < self.config.max_rounds:
            round_idx += 1
            is_last_round = round_idx >= self.config.max_rounds
            logger.info("Brainstorm round %d/%d (force_finalize=%s)",
                        round_idx, self.config.max_rounds, is_last_round)

            try:
                parsed = await self._invoke_llm(
                    service=service,
                    original_topic=original_topic,
                    force_finalize=is_last_round,
                )
            except SkipBrainstormException:
                logger.info("Brainstorm skipped by user/timeout at round %d", round_idx)
                return self._force_finalize(original_topic, reason="user_skip")
            except _BrainstormParseError as exc:
                logger.warning(
                    "Brainstorm LLM JSON parse failed after retries at round %d: %s",
                    round_idx, exc,
                )
                return self._force_finalize(original_topic, reason="parse_error")

            action = parsed.get("action")
            if action == "finalize" or is_last_round:
                if action != "finalize":
                    logger.warning(
                        "Round %d hit max_rounds but LLM still asked; forcing finalize.",
                        round_idx,
                    )
                return self._build_finalize_result(parsed, original_topic)

            if action == "ask":
                try:
                    await self._handle_ask(parsed, round_idx)
                except SkipBrainstormException:
                    logger.info(
                        "User skipped during round %d (after question shown).", round_idx,
                    )
                    return self._force_finalize(original_topic, reason="user_skip")
                continue

            # Unknown action — treat as parse failure and bail out gracefully.
            logger.warning(
                "Round %d returned unknown action=%r; forcing finalize.",
                round_idx, action,
            )
            return self._force_finalize(original_topic, reason="unknown_action")

        # Defensive: loop guard. Should be unreachable because is_last_round
        # path returns above, but keep as a safety net.
        logger.warning("Brainstorm exited loop without explicit finalize; falling back.")
        return self._force_finalize(original_topic, reason="loop_exhausted")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_service(self) -> ChatCompletionClientBase:
        """Look up the chat completion service from the kernel."""
        service = self.kernel.get_service(self.service_id)
        if not isinstance(service, ChatCompletionClientBase):
            raise TypeError(
                f"service_id={self.service_id!r} did not resolve to a "
                f"ChatCompletionClientBase (got {type(service).__name__})."
            )
        return service

    async def _invoke_llm(
        self,
        service: ChatCompletionClientBase,
        original_topic: str,
        force_finalize: bool,
    ) -> dict[str, Any]:
        """Call the moderator LLM and return the parsed JSON payload.

        Retries the LLM call once on JSON parse failure (AC3.2). On the
        second failure, raises ``_BrainstormParseError`` so the caller can
        fall back to ``original_topic``.
        """
        chat_history = self._build_chat_history(original_topic, force_finalize)
        last_error: Optional[Exception] = None

        for attempt in range(_JSON_RETRY_ATTEMPTS + 1):
            try:
                response = await service.get_chat_message_content(
                    chat_history,
                    settings=PromptExecutionSettings(),
                )
            except Exception as exc:  # noqa: BLE001
                # Network / provider errors are not JSON errors — re-raise so
                # the upper layer's own error handling kicks in.
                logger.exception("LLM call failed at attempt %d: %s", attempt + 1, exc)
                raise

            if response is None or not response.content:
                last_error = ValueError("LLM returned empty response")
                logger.warning(
                    "Empty LLM response on attempt %d/%d",
                    attempt + 1, _JSON_RETRY_ATTEMPTS + 1,
                )
                if attempt < _JSON_RETRY_ATTEMPTS:
                    self._add_repair_hint(chat_history, str(last_error))
                continue

            try:
                parsed = self._parse_llm_json(response.content)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "JSON parse failed on attempt %d/%d: %s | raw=%r",
                    attempt + 1, _JSON_RETRY_ATTEMPTS + 1, exc, response.content,
                )
                if attempt < _JSON_RETRY_ATTEMPTS:
                    self._add_repair_hint(chat_history, str(exc))
                continue

            return parsed

        raise _BrainstormParseError(
            f"Failed to parse LLM JSON after {_JSON_RETRY_ATTEMPTS + 1} attempts: {last_error}"
        )

    @staticmethod
    def _add_repair_hint(chat_history: ChatHistory, error: str) -> None:
        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content=(
                    f"Previous brainstorm output was invalid: {error}. "
                    "Return only a valid JSON object. "
                    + _FINALIZE_SCHEMA_REMINDER.strip()
                ),
            )
        )

    def _build_chat_history(self, original_topic: str, force_finalize: bool) -> ChatHistory:
        """Assemble a ChatHistory from system_prompt + accumulated turns."""
        chat_history = ChatHistory()

        system_prompt = self.config.system_prompt
        if force_finalize:
            system_prompt = (
                system_prompt
                + "\n\nThis is the last round, you MUST output action=finalize now."
                + _FINALIZE_SCHEMA_REMINDER
            )
        chat_history.add_message(
            ChatMessageContent(role=AuthorRole.SYSTEM, content=system_prompt)
        )

        # Seed the conversation with the user's original topic so the
        # moderator always has the anchor question in view.
        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content=f"Original topic: {original_topic}",
            )
        )

        for turn in self.history:
            role = AuthorRole.ASSISTANT if turn["role"] == "moderator" else AuthorRole.USER
            chat_history.add_message(
                ChatMessageContent(role=role, content=turn["content"])
            )

        return chat_history

    @staticmethod
    def _parse_llm_json(raw: str) -> dict[str, Any]:
        """Extract the JSON object from an LLM response.

        Tries strict ``json.loads`` first; if that fails, attempts to slice
        out the first ``{...}`` block. Validates that ``action`` is present.
        Raises ``json.JSONDecodeError``, ``KeyError`` or ``ValueError`` on
        unrecoverable problems so the caller can decide whether to retry.
        """
        text = raw.strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            payload = json.loads(text[start : end + 1])

        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object, got {type(payload).__name__}")

        # Validate required key per design.
        action = payload["action"]
        if action not in ("ask", "finalize"):
            raise ValueError(f"Unknown action={action!r}")
        if action == "finalize":
            BrainstormSession._validate_finalize_payload(payload)

        return payload

    @staticmethod
    def _validate_finalize_payload(payload: dict[str, Any]) -> None:
        """Validate fields that downstream dispatch depends on."""
        complexity = payload.get("complexity")
        if not isinstance(complexity, dict):
            raise ValueError("finalize missing structured complexity")
        level = str(complexity.get("level") or "").lower()
        if level not in {"low", "medium", "high"}:
            raise ValueError("finalize complexity.level must be low, medium, or high")
        if not str(complexity.get("rationale") or "").strip():
            raise ValueError("finalize complexity.rationale is required")

        dispatch_plan = payload.get("dispatch_plan")
        if not isinstance(dispatch_plan, dict):
            raise ValueError("finalize missing dispatch_plan")
        execution_mode = str(dispatch_plan.get("execution_mode") or "").lower()
        if execution_mode not in {"direct", "focused", "panel"}:
            raise ValueError("finalize dispatch_plan.execution_mode must be direct, focused, or panel")
        if not isinstance(dispatch_plan.get("tasks"), list):
            raise ValueError("finalize dispatch_plan.tasks must be a list")

    async def _handle_ask(self, parsed: dict[str, Any], round_idx: int) -> None:
        """Forward the moderator's question to the UI and wait for an answer.

        Mutates ``self.history`` in-place by appending both the moderator's
        question and the user's reply.
        """
        question = (parsed.get("question") or "").strip()
        if not question:
            # Defensive: an "ask" with no question is meaningless. Log and
            # treat as if the LLM had finalized so we don't spin forever.
            raise _BrainstormParseError("action=ask but no question provided")

        options = self._normalize_options(parsed.get("options") or [])
        allow_freeform = bool(
            parsed.get("allow_freeform", parsed.get("allow_freetext", True))
        )

        question_payload = {
            "id": f"brainstorm-{round_idx}",
            "question": question,
            "options": options,
            "allow_multiple": bool(parsed.get("allow_multiple", False)),
            "allow_freeform": allow_freeform,
            "round": round_idx,
            "max_rounds": self.config.max_rounds,
            "model": self.service_id,
        }
        logger.info(
            "Brainstorm round %d asking: %r (options=%d, freetext=%s)",
            round_idx, question, len(options), allow_freeform,
        )

        # Record the moderator's question *before* awaiting so that if the
        # user skips, the question is still visible in history.
        self.history.append({"role": "moderator", "content": question})

        answer = await self.on_question(question_payload)
        answer_str = (answer or "").strip()
        logger.info("Brainstorm round %d got user answer: %r", round_idx, answer_str)
        self.history.append({"role": "user", "content": answer_str})

    @staticmethod
    def _normalize_options(raw_options: Any) -> list[dict[str, str]]:
        """Normalize LLM option output into the frontend chip contract."""
        if not isinstance(raw_options, list):
            return []

        normalized: list[dict[str, str]] = []
        for index, option in enumerate(raw_options):
            if isinstance(option, dict):
                label = str(option.get("label") or option.get("text") or "").strip()
                option_id = str(option.get("id") or f"option-{index + 1}").strip()
            else:
                label = str(option).strip()
                option_id = f"option-{index + 1}"
            if label:
                normalized.append({"id": option_id, "label": label})
        return normalized

    def _build_finalize_result(
        self, parsed: dict[str, Any], original_topic: str
    ) -> dict:
        """Build the return payload for a successful LLM finalize.

        Falls back to ``original_topic`` if the LLM forgot to populate
        ``refined_topic`` (defensive — design says the prompt enforces it,
        but we should never crash here).
        """
        refined_topic = (parsed.get("refined_topic") or "").strip()
        if not refined_topic:
            logger.warning(
                "LLM finalize missing refined_topic; falling back to original_topic."
            )
            refined_topic = original_topic

        refined_topic = self._truncate_topic(refined_topic)
        context_summary = (parsed.get("context_summary") or "").strip()

        logger.info(
            "Brainstorm finalized: refined_topic=%r (len=%d) summary_len=%d history_turns=%d",
            refined_topic, len(refined_topic), len(context_summary), len(self.history),
        )

        return {
            "refined_topic": refined_topic,
            "context_summary": context_summary,
            "history": list(self.history),
            "complexity": parsed.get("complexity"),
            "dispatch_plan": parsed.get("dispatch_plan"),
        }

    def _force_finalize(self, original_topic: str, reason: str) -> dict:
        """Build a fallback finalize result without consulting the LLM.

        Used when the user skips, the LLM keeps producing garbage, or any
        other unrecoverable condition. ``refined_topic`` is set to
        ``original_topic`` (truncated) so downstream agents always have
        *something* to discuss.
        """
        logger.info(
            "Brainstorm force-finalize (reason=%s): using original_topic.", reason,
        )
        return {
            "refined_topic": self._truncate_topic(original_topic),
            "context_summary": "",
            "history": list(self.history),
            "complexity": self._fallback_complexity(reason),
            "dispatch_plan": None,
            "fallback_reason": reason,
        }

    @staticmethod
    def _fallback_complexity(reason: str) -> dict[str, Any]:
        reason_text = {
            "user_skip": "用户跳过议题精炼",
            "parse_error": "主持人输出解析失败",
            "unknown_action": "主持人输出了未知动作",
            "loop_exhausted": "主持人未在限定轮次内完成精炼",
        }.get(reason, "主持人未完成结构化精炼")
        return {
            "level": "medium",
            "rationale": f"{reason_text}，已按普通讨论处理。",
            "dimensions": [],
        }

    @staticmethod
    def _truncate_topic(topic: str) -> str:
        """Enforce AC2.5: refined_topic must be ≤ 300 chars, else …-suffixed."""
        if len(topic) <= _REFINED_TOPIC_MAX_CHARS:
            return topic
        # Reserve 1 char for the ellipsis so the final string is exactly the cap.
        return topic[: _REFINED_TOPIC_MAX_CHARS - 1] + "…"


class _BrainstormParseError(Exception):
    """Internal sentinel raised when LLM JSON parsing exhausts retries."""
