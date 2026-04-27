"""Discussion module: AgentGroupChat for initial discussion and follow-ups."""

import asyncio
import logging
import re
from collections.abc import Callable
from typing import Optional

from semantic_kernel.agents import ChatCompletionAgent, GroupChatOrchestration
from semantic_kernel.agents.orchestration.group_chat import (
    BooleanResult,
    GroupChatManager,
    MessageResult,
    StringResult,
)
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent
from semantic_kernel.functions import KernelArguments
from semantic_kernel.kernel import Kernel
from semantic_kernel.prompt_template import KernelPromptTemplate, PromptTemplateConfig

logger = logging.getLogger(__name__)


def _strip_hidden_reasoning(content: str) -> str:
    """Remove provider reasoning tags from user-visible discussion text."""
    content = re.sub(r"<think\b[^>]*>.*?</think>", "", content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r"<think\b[^>]*>.*$", "", content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r"</think>", "", content, flags=re.IGNORECASE)
    return content.strip()


def build_discussion_transcript(history: ChatHistory) -> str:
    """Render the visible discussion history into plain text."""
    lines: list[str] = []
    for message in history.messages:
        if message.role == AuthorRole.SYSTEM:
            continue
        content = (message.content or "").strip()
        if not content:
            continue
        speaker = message.name or message.role.value
        lines.append(f"[{speaker}] {content}")
    return "\n\n".join(lines)


class LLMGroupChatManager(GroupChatManager):
    """LLM-driven GroupChatManager.

    Note: should_terminate is NOT abstract - it has a default implementation
    with built-in max_rounds counting. Custom implementation MUST call
    super().should_terminate() to preserve the safety valve.
    """

    model_config = {"arbitrary_types_allowed": True}

    service: ChatCompletionClientBase
    topic: str
    selection_prompt: str = ""
    termination_prompt: str = ""
    result_filter_prompt: str = ""
    supports_structured_output: bool = True
    facilitator_name: str = "Host"
    facilitator_instructions: str = ""
    on_agent_selected: Optional[Callable[[str], None]] = None
    # Hard floor: never let the LLM terminate the discussion before this many
    # rounds have completed. Defends against the LLM judging "should end"
    # immediately after only seeing the initial topic. 0 = no floor.
    min_rounds: int = 0

    async def _render_prompt(self, prompt: str, arguments: KernelArguments) -> str:
        config = PromptTemplateConfig(template=prompt)
        template = KernelPromptTemplate(prompt_template_config=config)
        return await template.render(Kernel(), arguments=arguments)

    def _default_settings(self) -> PromptExecutionSettings:
        return PromptExecutionSettings()

    def _prepend_facilitator_instructions(self, prompt: str) -> str:
        """Merge facilitator instructions into the manager prompt."""
        if not self.facilitator_instructions.strip():
            return prompt
        return f"{self.facilitator_instructions.strip()}\n\n{prompt}"

    # --- Fallback parsers ---

    @staticmethod
    def _parse_boolean_result(content: str) -> BooleanResult:
        """Fallback: extract BooleanResult from LLM plain text response."""
        try:
            return BooleanResult.model_validate_json(content)
        except Exception:
            pass
        match = re.search(r'"result"\s*:\s*(true|false)', content, re.IGNORECASE)
        result = match.group(1).lower() == "true" if match else False
        reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', content)
        reason = reason_match.group(1) if reason_match else "Fallback parsed"
        return BooleanResult(result=result, reason=reason)

    @staticmethod
    def _parse_string_result(content: str) -> StringResult:
        """Fallback: extract StringResult from LLM plain text response."""
        try:
            return StringResult.model_validate_json(content)
        except Exception:
            pass
        match = re.search(r'\{[^}]*"result"\s*:\s*"([^"]+)"[^}]*\}', content)
        if match:
            return StringResult(result=match.group(1), reason="Fallback parsed")
        return StringResult(
            result=content.strip().split()[0] if content.strip() else "",
            reason="Fallback raw text",
        )

    # --- 3 abstract methods + 1 concrete method ---

    async def should_request_user_input(self, chat_history: ChatHistory) -> BooleanResult:
        return BooleanResult(result=False, reason="Pure agent discussion, no user input needed.")

    async def should_terminate(self, chat_history: ChatHistory) -> BooleanResult:
        # CRITICAL: Call super() first to preserve max_rounds safety valve
        # (super() also bumps current_round; we read it AFTER the call)
        base_result = await super().should_terminate(chat_history)
        if base_result.result:
            return base_result

        # Hard floor: don't let the LLM terminate before min_rounds completed.
        # current_round is 1-indexed after super() bumped it, so the very first
        # call has current_round == 1 (no agent has spoken yet at this point).
        if self.min_rounds > 0 and self.current_round <= self.min_rounds:
            logger.debug(
                f"should_terminate: enforcing min_rounds floor "
                f"(round {self.current_round}/{self.min_rounds}); not terminating."
            )
            return BooleanResult(
                result=False,
                reason=f"Minimum {self.min_rounds} rounds not yet reached "
                       f"(currently round {self.current_round}).",
            )

        # LLM-driven termination check
        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    self._prepend_facilitator_instructions(self.termination_prompt),
                    KernelArguments(topic=self.topic),
                ),
            ),
        )
        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content='Determine if the discussion should end. Respond JSON: {"result": true/false, "reason": "..."}',
            )
        )

        if self.supports_structured_output:
            response = await self.service.get_chat_message_content(
                chat_history, settings=PromptExecutionSettings(response_format=BooleanResult)
            )
            content = (response.content if response else "") or ""
            if content:
                try:
                    return BooleanResult.model_validate_json(content)
                except Exception:
                    logger.warning("should_terminate: structured parse failed, falling back to text parse")
            return self._parse_boolean_result(content)
        else:
            response = await self.service.get_chat_message_content(
                chat_history, settings=self._default_settings()
            )
            content = (response.content if response else "") or ""
            return self._parse_boolean_result(content)

    async def select_next_agent(
        self, chat_history: ChatHistory, participant_descriptions: dict[str, str]
    ) -> StringResult:
        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    self._prepend_facilitator_instructions(self.selection_prompt),
                    KernelArguments(
                        topic=self.topic,
                        participants="\n".join(
                            f"{k}: {v}" for k, v in participant_descriptions.items()
                        ),
                    ),
                ),
            ),
        )
        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content='Select next speaker. Respond JSON: {"result": "AgentName", "reason": "..."}',
            )
        )

        for attempt in range(3):
            try:
                if self.supports_structured_output:
                    response = await self.service.get_chat_message_content(
                        chat_history, settings=PromptExecutionSettings(response_format=StringResult)
                    )
                    content = (response.content if response else "") or ""
                    if content:
                        try:
                            result = StringResult.model_validate_json(content)
                        except Exception:
                            logger.warning("select_next_agent: structured parse failed attempt %d, falling back", attempt + 1)
                            result = self._parse_string_result(content)
                    else:
                        result = self._parse_string_result(content)
                else:
                    response = await self.service.get_chat_message_content(
                        chat_history, settings=self._default_settings()
                    )
                    content = (response.content if response else "") or ""
                    result = self._parse_string_result(content)
            except Exception:
                logger.warning("select_next_agent: LLM call failed attempt %d/3", attempt + 1)
                continue

            if result.result in participant_descriptions:
                logger.info(
                    "agent.selected name=%s reason=%s",
                    result.result,
                    result.reason,
                )
                if self.on_agent_selected is not None:
                    try:
                        self.on_agent_selected(result.result)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"on_agent_selected callback failed: {e}")
                return result
            logger.warning(f"LLM returned invalid agent name: {result.result}, retry {attempt + 1}/3")

        # Fallback: RoundRobin
        logger.warning("LLM selection failed, falling back to RoundRobin")
        fallback_name = list(participant_descriptions.keys())[
            self.current_round % len(participant_descriptions)
        ]
        logger.info("agent.selected name=%s reason=Fallback to RoundRobin", fallback_name)
        if self.on_agent_selected is not None:
            try:
                self.on_agent_selected(fallback_name)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"on_agent_selected callback failed: {e}")
        return StringResult(result=fallback_name, reason="Fallback to RoundRobin")

    async def filter_results(self, chat_history: ChatHistory) -> MessageResult:
        if not chat_history.messages:
            raise RuntimeError("Chat history is empty.")

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    self._prepend_facilitator_instructions(self.result_filter_prompt),
                    KernelArguments(topic=self.topic),
                ),
            ),
        )
        chat_history.add_message(
            ChatMessageContent(role=AuthorRole.USER, content="Please summarize the discussion.")
        )

        if self.supports_structured_output:
            response = await self.service.get_chat_message_content(
                chat_history, settings=PromptExecutionSettings(response_format=StringResult)
            )
            content = (response.content if response else "") or ""
            if content:
                try:
                    result = StringResult.model_validate_json(content)
                except Exception:
                    logger.warning("filter_results: structured parse failed, falling back to text parse")
                    result = self._parse_string_result(content)
            else:
                logger.warning("filter_results: LLM returned empty response, using transcript fallback")
                result = StringResult(result=build_discussion_transcript(chat_history), reason="Empty LLM response fallback")
        else:
            response = await self.service.get_chat_message_content(
                chat_history, settings=self._default_settings()
            )
            content = (response.content if response else "") or ""
            result = self._parse_string_result(content)

        return MessageResult(
            result=ChatMessageContent(role=AuthorRole.ASSISTANT, name=self.facilitator_name, content=result.result),
            reason=result.reason,
        )


async def run_discussion(
    agents: list[ChatCompletionAgent],
    topic: str,
    manager_service: ChatCompletionClientBase,
    manager_name: str,
    manager_instructions: str,
    max_rounds: int = 10,
    response_callback: Optional[Callable[[ChatMessageContent], None]] = None,
    supports_structured_output: bool = True,
    selection_prompt: str = "",
    termination_prompt: str = "",
    result_filter_prompt: str = "",
    on_agent_selected: Optional[Callable[[str], None]] = None,
) -> tuple[str, ChatHistory]:
    """Run the discussion phase. Returns (summary, chat_history)."""
    history = ChatHistory()
    history.add_message(ChatMessageContent(role=AuthorRole.USER, content=topic))

    summary = await _run_managed_group_chat(
        agents=agents,
        history=history,
        manager_service=manager_service,
        manager_name=manager_name,
        manager_instructions=manager_instructions,
        max_rounds=max_rounds,
        response_callback=response_callback,
        supports_structured_output=supports_structured_output,
        selection_prompt=selection_prompt,
        termination_prompt=termination_prompt,
        result_filter_prompt=result_filter_prompt,
        on_agent_selected=on_agent_selected,
    )

    return summary, history


async def run_followup(
    agents: list[ChatCompletionAgent],
    history: ChatHistory,
    followup_message: str,
    manager_service: ChatCompletionClientBase,
    manager_name: str,
    manager_instructions: str,
    response_callback: Callable[[ChatMessageContent], None],
    max_rounds: int = 3,
    supports_structured_output: bool = True,
    selection_prompt: str = "",
    termination_prompt: str = "",
    result_filter_prompt: str = "",
    on_agent_selected: Optional[Callable[[str], None]] = None,
) -> ChatHistory:
    """Run a follow-up discussion round with the same LLM-driven host."""
    history.add_message(ChatMessageContent(role=AuthorRole.USER, content=followup_message))

    await _run_managed_group_chat(
        agents=agents,
        history=history,
        manager_service=manager_service,
        manager_name=manager_name,
        manager_instructions=manager_instructions,
        max_rounds=max_rounds,
        response_callback=response_callback,
        supports_structured_output=supports_structured_output,
        selection_prompt=selection_prompt,
        termination_prompt=termination_prompt,
        result_filter_prompt=result_filter_prompt,
        on_agent_selected=on_agent_selected,
    )

    return history


async def _run_managed_group_chat(
    *,
    agents: list[ChatCompletionAgent],
    history: ChatHistory,
    manager_service: ChatCompletionClientBase,
    manager_name: str,
    manager_instructions: str,
    max_rounds: int,
    response_callback: Optional[Callable[[ChatMessageContent], None]],
    supports_structured_output: bool,
    selection_prompt: str,
    termination_prompt: str,
    result_filter_prompt: str,
    on_agent_selected: Optional[Callable[[str], None]] = None,
) -> str:
    """Run the managed group chat orchestration and return the final summary."""
    runtime = InProcessRuntime()
    # Force at least one full pass through every agent before the LLM is
    # allowed to vote for termination. Otherwise the LLM may judge "we can
    # stop" after seeing only the topic message — which is what produced
    # the "no agent ever spoke but we got a summary + votes" bug.
    min_rounds_floor = max(1, len(agents))
    agent_names = [getattr(agent, "name", type(agent).__name__) for agent in agents]
    logger.info(
        "discussion.start topic_len=%d agents=%s max_rounds=%s min_rounds=%s",
        len(history.messages[0].content or ""),
        ",".join(agent_names),
        max_rounds,
        min_rounds_floor,
    )
    manager = LLMGroupChatManager(
        service=manager_service,
        topic=history.messages[0].content or "",
        max_rounds=max_rounds,
        min_rounds=min_rounds_floor,
        supports_structured_output=supports_structured_output,
        facilitator_name=manager_name,
        facilitator_instructions=manager_instructions,
        selection_prompt=selection_prompt,
        termination_prompt=termination_prompt,
        result_filter_prompt=result_filter_prompt,
        on_agent_selected=on_agent_selected,
    )

    async def on_agent_response(message: ChatMessageContent) -> None:
        if message.role != AuthorRole.ASSISTANT:
            return
        cleaned_content = _strip_hidden_reasoning(message.content or "")
        if not cleaned_content:
            logger.warning(
                "agent.response hidden_only_skipped name=%s raw_len=%d",
                message.name or "Unknown",
                len(message.content or ""),
            )
            return
        if cleaned_content != (message.content or ""):
            message = ChatMessageContent(
                role=message.role,
                name=message.name,
                content=cleaned_content,
                metadata=getattr(message, "metadata", None),
            )
        logger.info(
            "agent.response name=%s content_len=%d",
            message.name or "Unknown",
            len(message.content or ""),
        )
        history.add_message(message)
        if response_callback:
            response_callback(message)

    orchestration = GroupChatOrchestration(
        members=agents,  # type: ignore[arg-type]
        manager=manager,
        agent_response_callback=on_agent_response,
    )

    runtime.start()
    force_stop_runtime = False
    try:
        logger.info("discussion.invoke runtime_started=true")
        result = await orchestration.invoke(task=history.messages[:], runtime=runtime)
        summary_message = await result.get(timeout=900)
    except TimeoutError:
        force_stop_runtime = True
        fallback_summary = build_discussion_transcript(history)
        if fallback_summary:
            logger.exception(
                "discussion.timed_out using_visible_transcript agents=%s transcript_len=%d",
                ",".join(agent_names),
                len(fallback_summary),
            )
            return fallback_summary
        logger.exception("discussion.timed_out no_visible_transcript agents=%s", ",".join(agent_names))
        raise
    except Exception:
        logger.exception("discussion.failed agents=%s", ",".join(agent_names))
        raise
    finally:
        if force_stop_runtime:
            try:
                await asyncio.wait_for(runtime.stop(), timeout=5)
            except Exception:  # noqa: BLE001
                logger.warning("discussion.runtime_force_stop_failed", exc_info=True)
        else:
            await runtime.stop_when_idle()
        logger.info("discussion.runtime_stopped")

    assert isinstance(summary_message, ChatMessageContent)  # nosec
    if summary_message.content:
        logger.info(
            "discussion.summary name=%s content_len=%d",
            summary_message.name or manager_name,
            len(summary_message.content or ""),
        )
        history.add_message(summary_message)
        return summary_message.content
    return build_discussion_transcript(history)
