"""FastAPI WebSocket server for agent-discussion frontend."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

from .brainstorm import BrainstormSession, SkipBrainstormException
from .discussion import (
    _strip_hidden_reasoning,
    build_discussion_transcript,
    run_discussion,
    run_followup,
)
from .loader import create_agent, create_service, load_config
from .models import AppConfig
from .reporting import save_report
from .voting import run_voting

logger = logging.getLogger(__name__)

app = FastAPI(title="Agent Discussion")

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"

# session_id -> Future（等待用户对当前 brainstorm 问题的回答）
# Key 优先使用前端传入的 client_session_id，兼容旧客户端时使用 id(websocket)。
pending_brainstorm_answers: dict[str, asyncio.Future] = {}
pending_topic_confirmations: dict[str, asyncio.Future] = {}


# Path-traversal hardening: only allow alphanumerics, dot, underscore, dash.
_SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9一-鿿._-]+$")


def _safe_resolve(base_dir: Path, user_input: str, expected_suffix: str | None = None) -> Path:
    """Resolve a user-supplied filename inside base_dir with 4 layers of defense.

    1. Length cap (<=128 chars) — prevents pathological inputs.
    2. Character whitelist — rejects path separators, NUL, unicode tricks.
    3. Suffix check — when expected_suffix is given, enforce file extension.
    4. Container check — resolved path must remain strictly inside base_dir.

    Raises HTTPException(400) on any violation. Never returns paths outside base_dir.
    """
    if not user_input or len(user_input) > 128:
        raise HTTPException(status_code=400, detail="Invalid name")
    if not _SAFE_NAME_PATTERN.match(user_input):
        raise HTTPException(status_code=400, detail="Invalid characters in name")
    if expected_suffix is not None and not user_input.endswith(expected_suffix):
        raise HTTPException(status_code=400, detail=f"Expected {expected_suffix} file")

    base_resolved = base_dir.resolve()
    candidate = (base_resolved / user_input).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path traversal blocked") from None
    return candidate


class BrainstormSkippedSignal(SkipBrainstormException):
    """Signal that user skipped the brainstorm phase via WS event."""


class _SingleServiceKernel:
    """Minimal service locator for BrainstormSession."""

    def __init__(self, service):
        self._service = service

    def get_service(self, _service_id: str):
        return self._service


def _default_config_path() -> str:
    import importlib.resources as pkg_resources
    ref = pkg_resources.files("src").joinpath("config/agents.yaml")
    with pkg_resources.as_file(ref) as path:
        return str(path)


class SessionState:
    """Holds per-session pipeline state."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.history = ChatHistory()
        self.discussion_transcript = ""
        self.discussion_result: str | None = None
        self.voting_result = None
        self.dispatch_state: dict[str, Any] | None = None
        self.final_solution: str | None = None
        self.review_result = None

        manager_cfg = config.agents[config.manager_service_index]
        self.manager_service = create_service(manager_cfg)
        self.manager_config = manager_cfg

        self.discussion_agents = []
        self.discussion_agent_map = {}
        self.final_agents = []
        for index, agent_cfg in enumerate(config.agents):
            if index == config.manager_service_index:
                continue
            agent = create_agent(agent_cfg)
            if agent_cfg.final_only:
                self.final_agents.append((agent_cfg, agent))
            else:
                self.discussion_agents.append(agent)
                self.discussion_agent_map[agent_cfg.name] = agent


def _interaction_key(websocket: WebSocket, data: dict[str, Any] | None = None) -> str:
    if data is not None:
        client_session_id = str(data.get("client_session_id") or "").strip()
        if client_session_id:
            return client_session_id
    return str(id(websocket))


def _find_pending_future(
    pending: dict[str, asyncio.Future],
    websocket: WebSocket,
    data: dict[str, Any],
) -> tuple[str, asyncio.Future | None]:
    keys = [_interaction_key(websocket, data), str(id(websocket))]
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        fut = pending.get(key)
        if fut is not None:
            return key, fut
    return keys[0], None


async def _send_json(websocket: WebSocket, data: dict[str, Any]) -> None:
    await websocket.send_text(json.dumps(_to_jsonable(data), ensure_ascii=False))


def _to_jsonable(value: Any) -> Any:
    """Convert SDK/Pydantic metadata into JSON-safe primitives."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_to_jsonable(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_jsonable(model_dump())
    legacy_dict = getattr(value, "dict", None)
    if callable(legacy_dict):
        return _to_jsonable(legacy_dict())
    return str(value)


async def wait_user_brainstorm_answer(
    session_id: str,
    ws: WebSocket,
    question_payload: dict,
    timeout_seconds: int,
) -> str:
    """Send moderator_question and await user answer or skip.

    Raises:
        BrainstormSkippedSignal: If user skipped or timed out.
    """
    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    pending_brainstorm_answers[session_id] = fut
    try:
        await _send_json(ws, {"type": "moderator_question", **question_payload})
        try:
            return await asyncio.wait_for(fut, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            await _send_json(ws, {"type": "brainstorm_timeout"})
            raise BrainstormSkippedSignal("answer timeout")
    finally:
        pending_brainstorm_answers.pop(session_id, None)


async def wait_user_topic_confirmation(
    session_id: str,
    timeout_seconds: int,
) -> str:
    """Wait for topic_confirmed or topic_refine_again. Timeout continues."""
    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    pending_topic_confirmations[session_id] = fut
    try:
        return await asyncio.wait_for(fut, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.info("topic confirmation timed out; continuing with refined topic")
        return "confirm"
    finally:
        pending_topic_confirmations.pop(session_id, None)


def _format_brainstorm_answer(data: dict[str, Any]) -> str:
    """Convert BrainstormAnswer payloads into compact text for the LLM."""
    if data.get("answer"):
        return str(data.get("answer", "")).strip()

    selected_ids = data.get("selected_option_ids") or []
    freeform = str(data.get("freeform_text") or "").strip()
    parts: list[str] = []
    if selected_ids:
        parts.append("Selected options: " + ", ".join(str(item) for item in selected_ids))
    if freeform:
        parts.append("Freeform answer: " + freeform)
    return "\n".join(parts).strip()


def _normalize_complexity(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    level = str(raw.get("level") or "medium").lower()
    if level not in {"low", "medium", "high"}:
        level = "medium"
    dimensions = raw.get("dimensions") or []
    if not isinstance(dimensions, list):
        dimensions = []
    return {
        "level": level,
        "rationale": str(raw.get("rationale") or "主持人未返回结构化复杂度，按普通讨论处理。"),
        "dimensions": [str(item) for item in dimensions if str(item).strip()],
    }


def _discussion_agent_configs(config: AppConfig) -> list[Any]:
    return [
        agent_cfg
        for index, agent_cfg in enumerate(config.agents)
        if index != config.manager_service_index and not agent_cfg.final_only
    ]


def _default_expected_final_output() -> str:
    return "输出清晰、可直接使用的最终推荐方案，并列出必要的取舍说明和待决策项。"


def _fallback_dispatch_tasks(config: AppConfig) -> list[dict[str, str]]:
    return [
        {
            "agent_name": agent_cfg.name,
            "sub_topic": "围绕精炼议题给出专业判断。",
            "expected_output": agent_cfg.description,
        }
        for agent_cfg in _discussion_agent_configs(config)
    ]


def _build_dispatch_state(
    *,
    original_topic: str,
    refined_topic: str,
    context_summary: str,
    raw_complexity: Any,
    raw_dispatch_plan: Any,
    config: AppConfig,
) -> dict[str, Any]:
    complexity = _normalize_complexity(raw_complexity)
    raw_plan = raw_dispatch_plan if isinstance(raw_dispatch_plan, dict) else {}
    available_names = [agent_cfg.name for agent_cfg in _discussion_agent_configs(config)]
    available = set(available_names)
    tasks_by_name: dict[str, dict[str, str]] = {}

    raw_tasks = raw_plan.get("tasks") or []
    if isinstance(raw_tasks, list):
        for task in raw_tasks:
            if not isinstance(task, dict):
                continue
            agent_name = str(task.get("agent_name") or "").strip()
            if not agent_name:
                continue
            if agent_name not in available:
                logger.warning("dispatch.invalid_agent name=%s", agent_name)
                continue
            if agent_name in tasks_by_name:
                logger.warning("dispatch.duplicate_agent name=%s", agent_name)
                continue
            sub_topic = str(task.get("sub_topic") or "").strip() or "围绕精炼议题给出专业判断。"
            normalized = {"agent_name": agent_name, "sub_topic": sub_topic}
            expected_output = str(task.get("expected_output") or "").strip()
            if expected_output:
                normalized["expected_output"] = expected_output
            tasks_by_name[agent_name] = normalized

    tasks = [tasks_by_name[name] for name in available_names if name in tasks_by_name]
    selected_agents = [task["agent_name"] for task in tasks]
    requested_mode = str(raw_plan.get("execution_mode") or raw_plan.get("mode") or "").strip().lower()
    if requested_mode not in {"direct", "focused", "panel"}:
        requested_mode = ""

    if requested_mode == "direct":
        execution_mode = "direct"
        tasks = []
        selected_agents = []
    elif selected_agents:
        execution_mode = requested_mode or (
            "focused" if len(selected_agents) < len(available_names) else "panel"
        )
    elif complexity["level"] == "low":
        execution_mode = "direct"
    else:
        execution_mode = "panel"
        tasks = _fallback_dispatch_tasks(config)
        selected_agents = [task["agent_name"] for task in tasks]

    expected_final_output = str(
        raw_plan.get("expected_final_output")
        or raw_plan.get("final_output")
        or _default_expected_final_output()
    ).strip()
    rationale = str(raw_plan.get("rationale") or "").strip()
    agent_tasks = {
        task["agent_name"]: {
            "task": task["sub_topic"],
            "expected_output": task.get("expected_output") or "",
        }
        for task in tasks
    }
    dispatch_plan = {
        "tasks": tasks,
        "rationale": rationale,
        "execution_mode": execution_mode,
        "selected_agents": selected_agents,
        "expected_final_output": expected_final_output,
    }
    return {
        "original_topic": original_topic,
        "refined_topic": refined_topic or original_topic,
        "context_summary": context_summary,
        "complexity": complexity,
        "execution_mode": execution_mode,
        "dispatch_plan": dispatch_plan,
        "selected_agents": selected_agents,
        "agent_tasks": agent_tasks,
        "expected_final_output": expected_final_output,
        "final_solution": None,
        "review_result": None,
    }


def _normalize_dispatch_plan(raw: Any, config: AppConfig) -> dict[str, Any]:
    state = _build_dispatch_state(
        original_topic="",
        refined_topic="",
        context_summary="",
        raw_complexity=None,
        raw_dispatch_plan=raw,
        config=config,
    )
    return state["dispatch_plan"]


def _build_brainstorm_config(config: AppConfig) -> Any:
    agent_lines = [
        f"- {agent_cfg.name}: {agent_cfg.description}"
        for agent_cfg in _discussion_agent_configs(config)
    ]
    roster = "\n".join(agent_lines) or "（无可派发讨论 agent）"
    system_prompt = (
        config.brainstorm.system_prompt
        + "\n\nAvailable discussion agents. dispatch_plan.tasks[].agent_name MUST use one of these exact names only:\n"
        + roster
        + "\n\nWhen finalizing, also include dispatch_plan.execution_mode as direct, focused, or panel, "
          "and dispatch_plan.expected_final_output describing the final answer shape."
    )
    return config.brainstorm.model_copy(update={"system_prompt": system_prompt})


def _selected_discussion_agents(session: SessionState) -> list[Any]:
    dispatch_state = getattr(session, "dispatch_state", None) or {}
    selected_names = dispatch_state.get("selected_agents") or []
    agent_map = getattr(session, "discussion_agent_map", None)
    if agent_map is None:
        agent_map = {
            getattr(agent, "name", type(agent).__name__): agent
            for agent in getattr(session, "discussion_agents", [])
        }
    return [agent_map[name] for name in selected_names if name in agent_map]


def _build_discussion_topic(topic: str, dispatch_state: dict[str, Any] | None) -> str:
    if not dispatch_state:
        return topic
    lines = [
        f"精炼议题：{topic}",
        "",
        "主持人派发任务如下。每位 agent 只回答自己名下任务，并避免替未派发 agent 发言。",
    ]
    for task in dispatch_state.get("dispatch_plan", {}).get("tasks", []):
        expected = task.get("expected_output") or "给出专业判断"
        lines.append(f"- {task['agent_name']}：{task['sub_topic']}（期望产出：{expected}）")
    if dispatch_state.get("expected_final_output"):
        lines.extend(["", f"最终产出要求：{dispatch_state['expected_final_output']}"])
    return "\n".join(lines)


def _build_synthesis_prompt(session: SessionState, topic: str, retry: bool = False) -> str:
    dispatch_state = getattr(session, "dispatch_state", None) or {}
    dispatch_plan = dispatch_state.get("dispatch_plan") or {}
    transcript = session.discussion_transcript or "（本轮未进入多 agent 讨论）"
    prompt = f"""请基于以下会话状态输出最终方案。

原始议题：
{dispatch_state.get("original_topic") or topic}

精炼议题：
{dispatch_state.get("refined_topic") or topic}

执行模式：
{dispatch_state.get("execution_mode") or "panel"}

派发计划：
{json.dumps(dispatch_plan, ensure_ascii=False)}

最终产出要求：
{dispatch_state.get("expected_final_output") or _default_expected_final_output()}

讨论记录：
{transcript}

输出要求：
- 直接给出最终推荐方案。
- 内容要可执行，不要只复述讨论。
- 不要输出 <think> 或隐藏推理。
"""
    if retry:
        prompt += "\n上一次输出为空。现在必须输出非空最终方案。"
    return prompt


def _build_synthesis_fallback(session: SessionState, topic: str) -> str:
    dispatch_state = getattr(session, "dispatch_state", None) or {}
    basis = _strip_hidden_reasoning(
        session.discussion_transcript
        or session.discussion_result
        or dispatch_state.get("context_summary", "")
        or topic
    )
    selected_agents = ", ".join(dispatch_state.get("selected_agents") or []) or "未派发讨论 agent"
    expected = dispatch_state.get("expected_final_output") or _default_expected_final_output()
    return (
        "## 最终推荐方案\n\n"
        "模型总结输出为空，以下内容根据当前会话状态生成。\n\n"
        f"- 精炼议题：{dispatch_state.get('refined_topic') or topic}\n"
        f"- 执行模式：{dispatch_state.get('execution_mode') or 'panel'}\n"
        f"- 已派发 agent：{selected_agents}\n"
        f"- 最终产出要求：{expected}\n\n"
        "### 可用依据\n\n"
        f"{basis or '当前没有可用讨论内容。'}"
    )


async def _run_synthesis_phase(websocket: WebSocket, session: SessionState, topic: str) -> str:
    logger.info("phase.synthesis.start agents=%d", len(session.final_agents))
    await _send_json(websocket, {"type": "phase", "phase": "synthesis", "label": "最终方案"})

    final_solution = ""
    if session.final_agents:
        for agent_cfg, agent in session.final_agents:
            logger.info("synthesis.invoke agent=%s", agent_cfg.name)
            response = await agent.get_response(
                messages=[ChatMessageContent(
                    role=AuthorRole.USER,
                    content=_build_synthesis_prompt(session, topic),
                )],
            )
            content = _strip_hidden_reasoning(response.message.content or "")
            if not content:
                logger.warning("synthesis.empty_retry agent=%s", agent_cfg.name)
                response = await agent.get_response(
                    messages=[ChatMessageContent(
                        role=AuthorRole.USER,
                        content=_build_synthesis_prompt(session, topic, retry=True),
                    )],
                )
                content = _strip_hidden_reasoning(response.message.content or "")
            final_solution = content or _build_synthesis_fallback(session, topic)
            message = ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                name=response.message.name or agent_cfg.name,
                content=final_solution,
            )
            session.history.add_message(message)
            logger.info(
                "synthesis.response agent=%s content_len=%d",
                agent_cfg.name,
                len(final_solution),
            )
            await _send_json(websocket, {
                "type": "message",
                "phase": "synthesis",
                "name": message.name or agent_cfg.name,
                "role": "assistant",
                "content": final_solution,
            })
    else:
        final_solution = _build_synthesis_fallback(session, topic)
        await _send_json(websocket, {
            "type": "message",
            "phase": "synthesis",
            "name": "Synthesizer",
            "role": "assistant",
            "content": final_solution,
        })

    session.final_solution = final_solution
    session.discussion_result = final_solution
    if session.dispatch_state is not None:
        session.dispatch_state["final_solution"] = final_solution
    return final_solution


async def _send_unselected_statuses(
    websocket: WebSocket,
    session: SessionState,
    spoken_agents: set[str],
) -> None:
    selected = set((getattr(session, "dispatch_state", None) or {}).get("selected_agents") or [])
    for agent_cfg in _discussion_agent_configs(session.config):
        if agent_cfg.name not in selected or agent_cfg.name not in spoken_agents:
            logger.info("agent.status skipped name=%s", agent_cfg.name)
            await _send_json(websocket, {
                "type": "agent_status",
                "name": agent_cfg.name,
                "status": "skipped",
            })


def _format_complexity_content(complexity: dict[str, Any]) -> str:
    label = {"low": "低", "medium": "中等", "high": "高"}[complexity["level"]]
    return f"复杂度判断：{label}\n\n{complexity['rationale']}"


def _format_dispatch_content(refined_topic: str, dispatch_plan: dict[str, Any]) -> str:
    tasks = dispatch_plan.get("tasks") or []
    mode_label = {
        "direct": "直接总结",
        "focused": "定向派发",
        "panel": "小组讨论",
    }.get(str(dispatch_plan.get("execution_mode") or ""), "小组讨论")
    lines = [
        f"派发计划已准备好。\n\n精炼议题：{refined_topic}",
        f"执行模式：{mode_label}",
    ]
    if dispatch_plan.get("expected_final_output"):
        lines.append(f"最终产出：{dispatch_plan['expected_final_output']}")
    for task in tasks:
        lines.append(f"- {task['agent_name']}：{task['sub_topic']}")
    if dispatch_plan.get("rationale"):
        lines.append(f"\n{dispatch_plan['rationale']}")
    return "\n".join(lines)


async def _send_host_message(
    websocket: WebSocket,
    session: SessionState,
    *,
    phase: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> None:
    await _send_json(websocket, {
        "type": "message",
        "phase": phase,
        "name": session.manager_config.name,
        "role": "assistant",
        "content": content,
        "meta": meta or {"variant": "normal"},
    })


async def _run_brainstorming_phase(
    websocket: WebSocket,
    session: SessionState,
    topic: str,
    interaction_key: str,
) -> dict[str, Any]:
    config = session.config

    await _send_json(websocket, {
        "type": "phase",
        "phase": "brainstorming",
        "label": "议题精炼",
    })

    async def on_question(question_payload: dict) -> str:
        await _send_host_message(
            websocket,
            session,
            phase="brainstorming",
            content=str(question_payload.get("question") or ""),
            meta={"variant": "normal"},
        )
        return await wait_user_brainstorm_answer(
            interaction_key,
            websocket,
            question_payload,
            config.brainstorm.answer_timeout_seconds,
        )

    while True:
        brainstorm = BrainstormSession(
            config=_build_brainstorm_config(config),
            kernel=_SingleServiceKernel(session.manager_service),
            service_id=session.manager_config.name,
            on_question=on_question,
        )
        result = await brainstorm.run(topic)
        refined_topic = result.get("refined_topic") or topic
        dispatch_state = _build_dispatch_state(
            original_topic=topic,
            refined_topic=refined_topic,
            context_summary=result.get("context_summary") or "",
            raw_complexity=result.get("complexity"),
            raw_dispatch_plan=result.get("dispatch_plan"),
            config=config,
        )

        if result.get("fallback_reason") == "user_skip":
            await _send_host_message(
                websocket,
                session,
                phase="brainstorming",
                content="已跳过议题精炼，将直接进入讨论。",
                meta={"variant": "normal"},
            )
            session.dispatch_state = dispatch_state
            return dispatch_state

        session.dispatch_state = dispatch_state
        complexity = dispatch_state["complexity"]
        dispatch_plan = dispatch_state["dispatch_plan"]
        payload = {
            "original_topic": dispatch_state["original_topic"],
            "refined_topic": dispatch_state["refined_topic"],
            "complexity": complexity,
            "dispatch_plan": dispatch_plan,
            "context_summary": dispatch_state["context_summary"],
            "execution_mode": dispatch_state["execution_mode"],
            "selected_agents": dispatch_state["selected_agents"],
            "expected_final_output": dispatch_state["expected_final_output"],
        }

        await _send_host_message(
            websocket,
            session,
            phase="brainstorming",
            content=_format_complexity_content(complexity),
            meta={"variant": "complexity", "complexity": complexity},
        )
        await _send_host_message(
            websocket,
            session,
            phase="brainstorming",
            content=_format_dispatch_content(refined_topic, dispatch_plan),
            meta={
                "variant": "dispatch",
                "dispatch": dispatch_plan,
                "refined_topic": refined_topic,
            },
        )
        await _send_json(websocket, {"type": "topic_refined", **payload})

        decision = await wait_user_topic_confirmation(
            interaction_key,
            config.brainstorm.answer_timeout_seconds,
        )
        if decision == "refine_again":
            topic = refined_topic
            await _send_host_message(
                websocket,
                session,
                phase="brainstorming",
                content="我会基于当前精炼结果继续追问一轮。",
                meta={"variant": "normal"},
            )
            continue
        return dispatch_state


async def _run_session_pipeline(
    websocket: WebSocket,
    session: SessionState,
    topic: str,
    interaction_key: str | None = None,
) -> None:
    """Run the full pipeline, streaming events over WebSocket."""
    config = session.config
    interaction_key = interaction_key or str(id(websocket))
    logger.info(
        "session.pipeline.start key=%s topic_len=%d discussion=%s voting=%s brainstorm=%s",
        interaction_key,
        len(topic),
        config.discussion.enabled,
        config.voting.enabled,
        config.brainstorm.enabled,
    )

    # --- Agent info ---
    agent_infos = []
    for agent_cfg in config.agents:
        agent_infos.append({
            "name": agent_cfg.name,
            "description": agent_cfg.description,
            "model": agent_cfg.model,
            "final_only": agent_cfg.final_only,
        })
    await _send_json(websocket, {"type": "agents", "agents": agent_infos})

    # Push agent_meta for new UI（设计文档第 4 节）：包含 model/role/is_moderator
    moderator_idx = config.manager_service_index
    agents_meta = []
    for i, agent_cfg in enumerate(config.agents):
        agents_meta.append({
            "name": agent_cfg.name,
            "model": agent_cfg.model,
            "role": agent_cfg.description,
            "is_moderator": i == moderator_idx,
        })
    await _send_json(websocket, {"type": "agent_meta", "agents": agents_meta})

    active_topic = topic
    if config.brainstorm.enabled:
        logger.info("phase.brainstorming.start")
        dispatch_state = await _run_brainstorming_phase(websocket, session, topic, interaction_key)
        active_topic = dispatch_state["refined_topic"]
        logger.info("phase.brainstorming.done refined_topic_len=%d", len(active_topic))
    else:
        session.dispatch_state = _build_dispatch_state(
            original_topic=topic,
            refined_topic=topic,
            context_summary="",
            raw_complexity=None,
            raw_dispatch_plan=None,
            config=config,
        )

    # --- Discussion phase ---
    selected_agents = _selected_discussion_agents(session)
    spoken_agents: set[str] = set()
    if config.discussion.enabled and selected_agents:
        logger.info(
            "phase.discussion.start agents=%s mode=%s",
            ",".join(getattr(agent, "name", type(agent).__name__) for agent in selected_agents),
            (session.dispatch_state or {}).get("execution_mode"),
        )
        await _send_json(websocket, {"type": "phase", "phase": "discussion", "label": "讨论阶段"})

        # Track which messages have been pushed to avoid duplicates
        pushed_message_set: set[int] = set()

        async def push_message(msg: ChatMessageContent, phase: str) -> None:
            msg_id = id(msg)
            if msg_id in pushed_message_set:
                return
            pushed_message_set.add(msg_id)
            role_value = msg.role.value if msg.role else "assistant"
            # Friendlier display name: user messages show "用户"; assistant fallback "匿名"
            if role_value == "user":
                display_name = msg.name or "用户"
            else:
                display_name = msg.name or "匿名"
            await _send_json(websocket, {
                "type": "message",
                "phase": phase,
                "name": display_name,
                "role": role_value,
                "content": msg.content or "",
                "meta": getattr(msg, "metadata", None),
            })

        # Use asyncio.Queue as bridge: the callback from GroupChatOrchestration is sync
        message_queue: asyncio.Queue[ChatMessageContent] = asyncio.Queue()
        # Separate queue for agent_status events (selected -> thinking)
        status_queue: asyncio.Queue[str] = asyncio.Queue()

        def sync_callback(msg: ChatMessageContent) -> None:
            message_queue.put_nowait(msg)

        def on_agent_selected(agent_name: str) -> None:
            logger.info("agent.status thinking name=%s", agent_name)
            status_queue.put_nowait(agent_name)

        async def drain_queue(phase: str) -> None:
            while True:
                try:
                    msg = message_queue.get_nowait()
                    await push_message(msg, phase)
                except asyncio.QueueEmpty:
                    break

        async def drain_status_queue() -> None:
            while True:
                try:
                    name = status_queue.get_nowait()
                    await _send_json(websocket, {
                        "type": "agent_status",
                        "name": name,
                        "status": "thinking",
                    })
                except asyncio.QueueEmpty:
                    break

        # Run discussion in background, drain queue periodically
        discussion_topic = _build_discussion_topic(active_topic, session.dispatch_state)
        discussion_task = asyncio.create_task(
            _run_discussion_phase(
                session,
                discussion_topic,
                sync_callback,
                on_agent_selected,
                agents=selected_agents,
            )
        )

        while not discussion_task.done():
            await drain_status_queue()
            await drain_queue("discussion")
            await asyncio.sleep(0.1)

        # Drain any remaining queued messages
        await drain_status_queue()
        await drain_queue("discussion")
        session.discussion_result, session.history = await discussion_task
        session.discussion_transcript = build_discussion_transcript(session.history)
        logger.info(
            "phase.discussion.done messages=%d transcript_len=%d",
            len(session.history.messages),
            len(session.discussion_transcript),
        )

        # Reconciliation: push any messages from history that were missed by the queue
        for msg in session.history.messages:
            if msg.role == AuthorRole.SYSTEM:
                continue
            content = (msg.content or "").strip()
            if not content:
                continue
            await push_message(msg, "discussion")
            if msg.name:
                spoken_agents.add(msg.name)

    else:
        logger.info(
            "phase.discussion.skipped enabled=%s selected_agents=%d mode=%s",
            config.discussion.enabled,
            len(selected_agents),
            (session.dispatch_state or {}).get("execution_mode"),
        )
        session.history = ChatHistory()
        session.history.add_message(ChatMessageContent(role=AuthorRole.USER, content=active_topic))
        session.discussion_transcript = ""

    await _send_unselected_statuses(websocket, session, spoken_agents)

    final_solution = await _run_synthesis_phase(websocket, session, active_topic)
    await _send_json(websocket, {
        "type": "summary",
        "content": final_solution,
    })

    # --- Voting phase ---
    review_agents = _selected_discussion_agents(session)
    if config.voting.enabled and review_agents:
        logger.info("phase.voting.start agents=%d", len(review_agents))
        await _send_json(websocket, {"type": "phase", "phase": "voting", "label": "方案评审"})

        session.voting_result = await run_voting(
            agents=review_agents,
            topic=active_topic,
            discussion_context=final_solution,
            voting_prompt=config.voting.prompt,
        )
        session.review_result = session.voting_result
        if session.dispatch_state is not None:
            session.dispatch_state["review_result"] = _to_jsonable(session.voting_result)

        votes_data = []
        for vote in session.voting_result.votes:
            votes_data.append({
                "agent_name": vote.agent_name,
                "stance": vote.stance,
                "reason": vote.reason,
                "confidence": vote.confidence,
            })

        await _send_json(websocket, {
            "type": "voting_result",
            "votes": votes_data,
            "conclusion": session.voting_result.conclusion,
        })
        logger.info("phase.voting.done votes=%d", len(votes_data))
    elif config.voting.enabled:
        logger.info("phase.voting.skipped no_selected_review_agents")

    await _send_json(websocket, {"type": "phase", "phase": "followup", "label": "后续交互"})
    await _send_json(websocket, {"type": "ready"})
    logger.info("session.pipeline.ready")


async def _run_discussion_phase(
    session: SessionState,
    topic: str,
    callback,
    on_agent_selected=None,
    agents: list[Any] | None = None,
) -> tuple[str, ChatHistory]:
    return await run_discussion(
        agents=agents if agents is not None else session.discussion_agents,
        topic=topic,
        manager_service=session.manager_service,
        manager_name=session.manager_config.name,
        manager_instructions=session.manager_config.instructions,
        max_rounds=session.config.discussion.max_rounds or 10,
        response_callback=callback,
        supports_structured_output=session.config.supports_structured_output,
        selection_prompt=session.config.discussion.selection_prompt,
        termination_prompt=session.config.discussion.termination_prompt,
        result_filter_prompt=session.config.discussion.result_filter_prompt,
        on_agent_selected=on_agent_selected,
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    config_path = _default_config_path()
    try:
        app_config = load_config(config_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load config: %s", exc)
        await _send_json(websocket, {"type": "error", "message": str(exc)})
        await websocket.close(code=1011)
        return
    session: SessionState | None = None
    pipeline_task: asyncio.Task | None = None

    async def run_pipeline_safe(active_session: SessionState, topic: str, interaction_key: str) -> None:
        try:
            await _run_session_pipeline(websocket, active_session, topic, interaction_key)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Session pipeline failed")
            await _send_json(websocket, {"type": "error", "message": str(exc)})

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            action = data.get("action") or data.get("type")

            if action == "start":
                topic = data.get("topic", "").strip()
                if not topic:
                    await _send_json(websocket, {"type": "error", "message": "话题不能为空"})
                    continue

                if pipeline_task is not None and not pipeline_task.done():
                    pipeline_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await pipeline_task

                session = SessionState(app_config)
                await _send_json(websocket, {"type": "started", "topic": topic})
                interaction_key = _interaction_key(websocket, data)
                pipeline_task = asyncio.create_task(run_pipeline_safe(session, topic, interaction_key))

            elif action == "followup":
                if session is None:
                    await _send_json(websocket, {"type": "error", "message": "请先开始一个讨论"})
                    continue
                if pipeline_task is not None and not pipeline_task.done():
                    await _send_json(websocket, {"type": "error", "message": "讨论仍在进行中"})
                    continue
                followup_text = data.get("message", "").strip()
                if not followup_text:
                    continue
                followup_agents = _selected_discussion_agents(session)
                if not followup_agents:
                    await _send_json(websocket, {
                        "type": "error",
                        "message": "当前会话未派发讨论 agent，无法继续多 agent 追问。",
                    })
                    continue

                await _send_json(websocket, {"type": "phase", "phase": "followup_round", "label": "追问讨论"})

                # Snapshot history length before followup to reconcile new messages later
                history_len_before = len(session.history.messages)
                pushed_followup_ids: set[int] = set()

                followup_queue: asyncio.Queue[ChatMessageContent] = asyncio.Queue()

                def followup_callback(msg: ChatMessageContent) -> None:
                    followup_queue.put_nowait(msg)

                async def push_followup_msg(msg: ChatMessageContent) -> None:
                    msg_id = id(msg)
                    if msg_id in pushed_followup_ids:
                        return
                    pushed_followup_ids.add(msg_id)
                    role_value = msg.role.value if msg.role else "assistant"
                    if role_value == "user":
                        display_name = msg.name or "用户"
                    else:
                        display_name = msg.name or "匿名"
                    await _send_json(websocket, {
                        "type": "message",
                        "phase": "followup",
                        "name": display_name,
                        "role": role_value,
                        "content": msg.content or "",
                    })

                followup_task = asyncio.create_task(
                    run_followup(
                        agents=followup_agents,
                        history=session.history,
                        followup_message=followup_text,
                        manager_service=session.manager_service,
                        manager_name=session.manager_config.name,
                        manager_instructions=session.manager_config.instructions,
                        response_callback=followup_callback,
                        max_rounds=session.config.discussion.max_rounds or 5,
                        supports_structured_output=session.config.supports_structured_output,
                        selection_prompt=session.config.discussion.selection_prompt,
                        termination_prompt=session.config.discussion.termination_prompt,
                        result_filter_prompt=session.config.discussion.result_filter_prompt,
                    )
                )

                while not followup_task.done():
                    while True:
                        try:
                            msg = followup_queue.get_nowait()
                            await push_followup_msg(msg)
                        except asyncio.QueueEmpty:
                            break
                    await asyncio.sleep(0.1)

                # Drain remaining queued messages
                while True:
                    try:
                        msg = followup_queue.get_nowait()
                        await push_followup_msg(msg)
                    except asyncio.QueueEmpty:
                        break

                session.history = await followup_task
                session.discussion_transcript = build_discussion_transcript(session.history)

                # Reconciliation: push any new messages from history that were missed
                for msg in session.history.messages[history_len_before:]:
                    if msg.role == AuthorRole.SYSTEM:
                        continue
                    content = (msg.content or "").strip()
                    if not content:
                        continue
                    await push_followup_msg(msg)

                await _send_json(websocket, {"type": "ready"})

            elif action == "save":
                if session is None:
                    await _send_json(websocket, {"type": "error", "message": "没有可保存的讨论"})
                    continue
                if pipeline_task is not None and not pipeline_task.done():
                    await _send_json(websocket, {"type": "error", "message": "讨论仍在进行中"})
                    continue
                report_path = save_report(
                    topic=data.get("topic", "discussion"),
                    discussion_summary=session.final_solution or session.discussion_result or "",
                    discussion_transcript=session.discussion_transcript,
                    voting_result=session.voting_result,
                    dispatch_state=session.dispatch_state,
                )
                await _send_json(websocket, {
                    "type": "saved",
                    "path": str(report_path),
                })

            elif action == "moderator_answer":
                # 用户回答主持人的 brainstorm 提问；解锁 wait_user_brainstorm_answer 中等待的 future
                pending_key, fut = _find_pending_future(pending_brainstorm_answers, websocket, data)
                if fut is not None and not fut.done():
                    fut.set_result(_format_brainstorm_answer(data))
                else:
                    logger.warning(
                        "moderator_answer received but no pending future key=%s ws=%s",
                        pending_key,
                        id(websocket),
                    )

            elif action == "brainstorm_skip":
                # 用户主动跳过 brainstorm 阶段；通过 set_exception 让等待方收到 BrainstormSkippedSignal
                pending_key, fut = _find_pending_future(pending_brainstorm_answers, websocket, data)
                if fut is not None and not fut.done():
                    fut.set_exception(BrainstormSkippedSignal("user skip"))
                else:
                    logger.warning(
                        "brainstorm_skip received but no pending future key=%s ws=%s",
                        pending_key,
                        id(websocket),
                    )

            elif action == "topic_confirmed":
                # 用户确认精炼后的议题；当前阶段仅记录，实际接入由后续阶段完成
                logger.info(
                    f"topic_confirmed for ws={id(websocket)}: {data}"
                )
                _pending_key, fut = _find_pending_future(pending_topic_confirmations, websocket, data)
                if fut is not None and not fut.done():
                    fut.set_result("confirm")

            elif action == "topic_refine_again":
                _pending_key, fut = _find_pending_future(pending_topic_confirmations, websocket, data)
                if fut is not None and not fut.done():
                    fut.set_result("refine_again")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.exception("WebSocket error")
        try:
            await _send_json(websocket, {"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        if pipeline_task is not None and not pipeline_task.done():
            pipeline_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pipeline_task



SESSIONS_DIR = Path(__file__).resolve().parents[1] / "sessions"
DIST_DIR = FRONTEND_DIR / "dist"


@app.get('/api/reports')
async def list_reports():
    """List saved historical reports from report/ directory."""
    report_dir = Path(__file__).resolve().parents[1] / 'report'

    if not report_dir.exists():
        return {"reports": []}

    reports = []
    for md_file in report_dir.glob('*.md'):
        stat = md_file.stat()
        filename = md_file.name
        size_bytes = stat.st_size
        modified_at = stat.st_mtime

        topic = ""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= 5:
                        break
                    if line.startswith('- 讨论话题：'):
                        topic = line[len('- 讨论话题：'):].strip()
                        break
        except Exception:
            pass

        reports.append({
            'filename': filename,
            'topic': topic,
            'size_bytes': size_bytes,
            'modified_at': modified_at,
            'path': str(md_file),
        })

    reports.sort(key=lambda x: x['modified_at'], reverse=True)
    return {"reports": reports}


@app.get('/api/reports/{filename}')
async def get_report(filename: str):
    """Read a single report file content (path-traversal hardened)."""
    from fastapi.responses import PlainTextResponse

    report_dir = Path(__file__).resolve().parents[1] / 'report'
    file_path = _safe_resolve(report_dir, filename, expected_suffix='.md')

    if not file_path.exists() or not file_path.is_file():
        return PlainTextResponse("报告不存在", status_code=404)
    content = file_path.read_text(encoding='utf-8')
    return PlainTextResponse(content)


@app.post('/api/sessions')
async def save_session(request_data: dict):
    """Save session data to JSON file (path-traversal hardened)."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    raw_id = request_data.get('id') or str(uuid.uuid4())

    # Validate session id strictly. If user supplied a bad id, fall back to a fresh UUID
    # rather than 400-ing — keeps the UX smooth while still preventing traversal.
    if not isinstance(raw_id, str) or not _SAFE_NAME_PATTERN.match(raw_id) or len(raw_id) > 128:
        raw_id = str(uuid.uuid4())

    # _safe_resolve also enforces the .json suffix and containment.
    file_path = _safe_resolve(SESSIONS_DIR, f"{raw_id}.json", expected_suffix='.json')
    # Ensure id in stored data matches the sanitized one (defense in depth).
    request_data['id'] = raw_id
    file_path.write_text(json.dumps(request_data, ensure_ascii=False, indent=2), encoding='utf-8')
    return {"status": "ok", "id": raw_id, "path": str(file_path)}


@app.get('/api/sessions')
async def list_sessions():
    """List saved sessions."""
    if not SESSIONS_DIR.exists():
        return {"sessions": []}
    sessions = []
    for json_file in SESSIONS_DIR.glob('*.json'):
        try:
            data = json.loads(json_file.read_text(encoding='utf-8'))
            sessions.append({
                "id": data.get("id", json_file.stem),
                "topic": data.get("topic", ""),
                "messageCount": len(data.get("messages", [])),
                "createdAt": data.get("createdAt", 0),
                "updatedAt": data.get("updatedAt", 0),
            })
        except Exception:
            continue
    sessions.sort(key=lambda x: x['updatedAt'], reverse=True)
    return {"sessions": sessions}


@app.get('/api/sessions/{session_id}')
async def get_session(session_id: str):
    """Get a single session (path-traversal hardened)."""
    from fastapi.responses import JSONResponse

    file_path = _safe_resolve(SESSIONS_DIR, f"{session_id}.json", expected_suffix='.json')
    if not file_path.exists() or not file_path.is_file():
        return JSONResponse({"error": "Session not found"}, status_code=404)
    data = json.loads(file_path.read_text(encoding='utf-8'))
    return data


@app.get("/")
async def serve_index():
    """Serve index.html - prefer Vite dist/ build, fallback to frontend/."""
    dist_index = DIST_DIR / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)
    frontend_index = FRONTEND_DIR / "index.html"
    if frontend_index.exists():
        return FileResponse(frontend_index)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("Frontend not built. Run: cd frontend && npm run build", status_code=404)


# Serve Vite dist/ assets first, then fallback to frontend/
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="dist-assets")
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
