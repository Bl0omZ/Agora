from __future__ import annotations

import ast
import json
import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

from .text_safety import strip_hidden_reasoning


BlueprintStatus = Literal["draft", "reviewed", "exported"]
OutputFormat = Literal["markdown", "json", "yaml", "mixed"]
GenerationSource = Literal["model", "retry", "deterministic_fallback"]


class InputContract(BaseModel):
    description: str = ""
    examples: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)


class OutputContract(BaseModel):
    description: str = ""
    format: OutputFormat = "markdown"
    required_sections: list[str] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    id: str
    name: str
    owner_agent: str = ""
    input: str = ""
    output: str = ""
    next: list[str] = Field(default_factory=list)
    error_path: str = ""


class WorkflowSpec(BaseModel):
    steps: list[WorkflowStep] = Field(default_factory=list)


class ModelPreferences(BaseModel):
    preferred_model: str | None = None
    fallback_model: str | None = None


class ToolPermissions(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)


class FailureHandling(BaseModel):
    empty_response: str = "Ask the user for missing context."
    invalid_output: str = "Retry with stricter schema instructions."
    timeout: str = "Return a partial result with warnings."


class BlueprintAgentSpec(BaseModel):
    name: str
    role: str = ""
    goal: str = ""
    instructions: str = ""
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    collaboration_rules: list[str] = Field(default_factory=list)
    model_preferences: ModelPreferences = Field(default_factory=ModelPreferences)
    tool_permissions: ToolPermissions = Field(default_factory=ToolPermissions)
    failure_handling: FailureHandling = Field(default_factory=FailureHandling)


class ToolSpec(BaseModel):
    name: str
    purpose: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class EvaluationSpec(BaseModel):
    criteria: list[str | dict[str, Any]] = Field(default_factory=list)
    test_cases: list[str] = Field(default_factory=list)


class RiskSpec(BaseModel):
    risk: str
    mitigation: str = ""
    severity: Literal["low", "medium", "high"] = "medium"


class ExportRecord(BaseModel):
    format: str
    created_at: float | None = None
    warnings: list[str] = Field(default_factory=list)


class GenerationMeta(BaseModel):
    source: GenerationSource = "model"
    warnings: list[str] = Field(default_factory=list)


class AgentSystemBlueprint(BaseModel):
    schema_version: int = 1
    id: str = Field(default_factory=lambda: f"bp_{uuid.uuid4().hex[:12]}")
    project_id: str | None = None
    session_id: str | None = None
    name: str
    status: BlueprintStatus = "draft"
    created_at: float | None = None
    updated_at: float | None = None
    problem_statement: str
    target_user: str | list[Any] | dict[str, Any] = ""
    use_cases: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    input_contract: InputContract = Field(default_factory=InputContract)
    output_contract: OutputContract = Field(default_factory=OutputContract)
    workflow: WorkflowSpec = Field(default_factory=WorkflowSpec)
    agents: list[BlueprintAgentSpec] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)
    evaluation: EvaluationSpec = Field(default_factory=EvaluationSpec)
    risks: list[RiskSpec] = Field(default_factory=list)
    exports: list[ExportRecord] = Field(default_factory=list)
    generation: GenerationMeta = Field(default_factory=GenerationMeta)


class BlueprintGenerationResult(BaseModel):
    blueprint: AgentSystemBlueprint
    warnings: list[str] = Field(default_factory=list)


def _cleanup_value(value: Any) -> Any:
    if isinstance(value, str):
        return strip_hidden_reasoning(value)
    if isinstance(value, list):
        return [_cleanup_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _cleanup_value(item) for key, item in value.items()}
    return value


def parse_blueprint_response(content: str, *, session_id: str | None) -> AgentSystemBlueprint:
    cleaned = strip_hidden_reasoning(content)
    data = json.loads(_extract_json_payload(cleaned))
    data = _cleanup_value(data)
    data.setdefault("session_id", session_id)
    data = _normalize_blueprint_payload(data)
    return AgentSystemBlueprint.model_validate(data)


def _normalize_blueprint_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("blueprint payload must be a JSON object")

    normalized = dict(data)
    version = normalized.get("schema_version")
    if isinstance(version, str):
        try:
            normalized["schema_version"] = int(float(version))
        except ValueError:
            normalized["schema_version"] = 1

    if normalized.get("status") not in {"draft", "reviewed", "exported"}:
        normalized["status"] = "draft"

    normalized["target_user"] = _normalize_target_user(normalized.get("target_user"))
    normalized["use_cases"] = _normalize_string_list(normalized.get("use_cases"))
    normalized["non_goals"] = _normalize_string_list(normalized.get("non_goals"))

    input_contract = normalized.get("input_contract")
    if isinstance(input_contract, dict):
        required = input_contract.get("required")
        if required and "description" not in input_contract:
            input_contract["description"] = str(required)
        if isinstance(required, str) and not input_contract.get("required_fields"):
            input_contract["required_fields"] = [required]
        input_contract["examples"] = _normalize_string_list(input_contract.get("examples"))
        input_contract["required_fields"] = _normalize_string_list(input_contract.get("required_fields"))

    output_contract = normalized.get("output_contract")
    if isinstance(output_contract, dict):
        ticket_format = output_contract.get("ticket_format")
        if ticket_format and "description" not in output_contract:
            output_contract["description"] = str(ticket_format)
        fields = output_contract.get("fields")
        if isinstance(fields, list) and not output_contract.get("required_sections"):
            output_contract["required_sections"] = [str(field) for field in fields]
        output_contract["required_sections"] = _normalize_string_list(
            output_contract.get("required_sections")
        )
        fmt = output_contract.get("format")
        if fmt not in ("markdown", "json", "yaml", "mixed"):
            output_contract["format"] = "markdown"

    workflow = normalized.get("workflow")
    if isinstance(workflow, list):
        normalized["workflow"] = {
            "steps": [
                _normalize_workflow_step(item, index)
                for index, item in enumerate(workflow, start=1)
            ]
        }
    elif isinstance(workflow, dict) and isinstance(workflow.get("steps"), list):
        workflow["steps"] = [
            _normalize_workflow_step(item, index)
            for index, item in enumerate(workflow["steps"], start=1)
        ]

    agents = normalized.get("agents")
    if isinstance(agents, list):
        normalized["agents"] = [
            _normalize_agent_spec(item, index)
            for index, item in enumerate(agents, start=1)
        ]

    workflow = normalized.get("workflow")
    if not isinstance(workflow, dict):
        normalized["workflow"] = {"steps": []}
    if not normalized["workflow"].get("steps") and normalized.get("agents"):
        normalized["workflow"]["steps"] = _default_workflow_steps(normalized["agents"])

    tools = normalized.get("tools")
    if isinstance(tools, list):
        normalized["tools"] = [
            _normalize_tool_spec(item, index)
            for index, item in enumerate(tools, start=1)
        ]

    evaluation = normalized.get("evaluation")
    if isinstance(evaluation, dict):
        metrics = evaluation.get("metrics")
        if isinstance(metrics, list) and not evaluation.get("criteria"):
            evaluation["criteria"] = [str(metric) for metric in metrics]
        methods = evaluation.get("methods")
        targets = evaluation.get("targets")
        test_cases = evaluation.get("test_cases")
        if not test_cases:
            evaluation["test_cases"] = _normalize_string_list(methods)
            if isinstance(targets, dict):
                evaluation["test_cases"].extend(
                    f"{key}: {value}" for key, value in targets.items()
                )
        evaluation["criteria"] = _normalize_criteria_list(evaluation.get("criteria"))
        evaluation["test_cases"] = _normalize_string_list(evaluation.get("test_cases"))

    risks = normalized.get("risks")
    if isinstance(risks, list):
        normalized["risks"] = [
            _normalize_risk_spec(item)
            for item in risks
        ]

    exports = normalized.get("exports")
    if isinstance(exports, list):
        normalized["exports"] = [_normalize_export_record(item) for item in exports]
    else:
        normalized["exports"] = []

    generation = normalized.get("generation")
    if isinstance(generation, str):
        normalized["generation"] = {"source": "model", "warnings": [generation]}
    elif isinstance(generation, dict):
        if generation.get("source") not in {"model", "retry", "deterministic_fallback"}:
            generation["source"] = "model"
        generation["warnings"] = _normalize_string_list(generation.get("warnings"))
        if generation["source"] in {"model", "retry"}:
            generation["warnings"] = [
                warning
                for warning in generation["warnings"]
                if not _is_format_validation_warning(warning)
            ]
    else:
        normalized["generation"] = {"source": "model", "warnings": []}

    return normalized


def _parse_structured_string(value: str) -> Any:
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return value


def _normalize_target_user(value: Any) -> Any:
    if isinstance(value, str):
        parsed = _parse_structured_string(value)
        if parsed is not value and isinstance(parsed, (list, dict)):
            return parsed
    if isinstance(value, dict):
        if "primary" in value or "secondary" in value:
            return _compact_string(value)
        return value
    if isinstance(value, list):
        return value
    return _compact_string(value)


def _compact_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts: list[str] = []
        primary = value.get("primary")
        if primary:
            parts.append(str(primary))
        secondary = value.get("secondary")
        if isinstance(secondary, list):
            parts.extend(str(item) for item in secondary)
        elif secondary:
            parts.append(str(secondary))
        if parts:
            return "; ".join(parts)
    return json.dumps(value, ensure_ascii=False)


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]

    results: list[str] = []
    for item in value:
        if isinstance(item, str):
            results.append(item)
        elif isinstance(item, dict):
            title = item.get("title") or item.get("name") or item.get("id")
            description = item.get("description")
            if title and description:
                results.append(f"{title}: {description}")
            elif title:
                results.append(str(title))
            else:
                results.append(json.dumps(item, ensure_ascii=False))
        else:
            results.append(str(item))
    return results


def _normalize_criteria_list(value: Any) -> list[str | dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]

    results: list[str | dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            parsed = _parse_structured_string(item)
            if isinstance(parsed, dict):
                results.append(parsed)
            elif isinstance(parsed, list):
                results.extend(_normalize_criteria_list(parsed))
            else:
                results.append(item)
        elif isinstance(item, dict):
            results.append(item)
        else:
            results.append(str(item))
    return results


def _default_workflow_steps(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for index, agent in enumerate(agents, start=1):
        name = str(agent.get("name") or f"Agent {index}")
        steps.append(
            {
                "id": f"step_{index}",
                "name": f"{name} 执行",
                "owner_agent": name,
                "input": "上一步输出或用户输入",
                "output": "; ".join(_normalize_string_list(agent.get("outputs")))
                or _compact_string(agent.get("goal"))
                or "阶段产出",
                "next": [f"step_{index + 1}"] if index < len(agents) else [],
                "error_path": "返回错误说明并请求补充信息",
            }
        )
    return steps


def _is_format_validation_warning(warning: str) -> bool:
    return any(
        marker in warning
        for marker in (
            "格式校验",
            "JSONDecodeError",
            "ValidationError",
            "blueprint payload",
        )
    )


def _normalize_agent_spec(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": f"Agent {index}", "role": str(item)}

    agent = dict(item)
    name = agent.get("name") or agent.get("id") or agent.get("role") or f"Agent {index}"
    agent["name"] = str(name)
    agent["role"] = _compact_string(agent.get("role"))
    if not agent.get("goal") and agent.get("description"):
        agent["goal"] = str(agent["description"])
    if not agent.get("instructions") and agent.get("description"):
        agent["instructions"] = str(agent["description"])
    agent["goal"] = _compact_string(agent.get("goal"))
    agent["instructions"] = _compact_string(agent.get("instructions"))
    agent["inputs"] = _normalize_string_list(agent.get("inputs"))
    capabilities = agent.get("capabilities")
    if isinstance(capabilities, list) and not agent.get("outputs"):
        agent["outputs"] = [str(capability) for capability in capabilities]
    agent["outputs"] = _normalize_string_list(agent.get("outputs"))
    agent["collaboration_rules"] = _normalize_string_list(agent.get("collaboration_rules"))
    if not isinstance(agent.get("model_preferences"), dict):
        preferred = agent.get("model_hint") or agent.get("model_preferences")
        agent["model_preferences"] = {"preferred_model": str(preferred)} if preferred else {}
    permissions = agent.get("tool_permissions")
    if isinstance(permissions, list):
        agent["tool_permissions"] = {"allowed_tools": _normalize_string_list(permissions)}
    elif isinstance(permissions, dict):
        permissions["allowed_tools"] = _normalize_string_list(permissions.get("allowed_tools"))
        permissions["forbidden_tools"] = _normalize_string_list(permissions.get("forbidden_tools"))
    elif permissions is not None:
        agent["tool_permissions"] = {"allowed_tools": _normalize_string_list(permissions)}
    failure = agent.get("failure_handling")
    if failure is not None and not isinstance(failure, dict):
        agent["failure_handling"] = {}
    return agent


def _normalize_tool_spec(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": f"Tool {index}", "purpose": str(item)}

    tool = dict(item)
    tool["name"] = str(tool.get("name") or tool.get("id") or f"Tool {index}")
    tool["purpose"] = _compact_string(tool.get("purpose") or tool.get("description"))
    if not isinstance(tool.get("input_schema"), dict):
        tool["input_schema"] = {}
    if not isinstance(tool.get("output_schema"), dict):
        tool["output_schema"] = {}
    return tool


def _normalize_risk_spec(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"risk": item}
    if not isinstance(item, dict):
        return {"risk": str(item)}

    risk = dict(item)
    risk.setdefault("risk", risk.get("title") or risk.get("description") or risk.get("id") or "Unspecified risk")
    risk["risk"] = _compact_string(risk.get("risk"))
    risk["mitigation"] = _compact_string(risk.get("mitigation"))
    severity = str(risk.get("severity") or "").lower()
    if severity not in {"low", "medium", "high"}:
        risk["severity"] = "high" if severity in {"critical", "severe"} else "medium"
    else:
        risk["severity"] = severity
    return risk


def _normalize_export_record(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        record = dict(item)
        record["format"] = str(record.get("format") or record.get("type") or "notes")
        record["warnings"] = _normalize_string_list(record.get("warnings"))
        if not isinstance(record.get("created_at"), (int, float)):
            record["created_at"] = None
        return record
    return {"format": "notes", "warnings": _normalize_string_list(item)}


def _normalize_workflow_step(item: Any, index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        step = dict(item)
        step.setdefault("id", f"step_{index}")
        step.setdefault("name", str(step.get("output") or f"Step {index}"))
        step["input"] = _compact_string(step.get("input"))
        step["output"] = _compact_string(step.get("output"))
        step["error_path"] = _compact_string(step.get("error_path"))
        next_steps = step.get("next")
        if isinstance(next_steps, list):
            step["next"] = _normalize_string_list(next_steps)
        elif next_steps:
            step["next"] = [str(next_steps)]
        return step

    text = str(item)
    name, _, detail = text.partition(":")
    return {
        "id": f"step_{index}",
        "name": name.strip() or f"Step {index}",
        "output": detail.strip() or text,
    }


def _extract_json_payload(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start:end + 1]

    return stripped


def build_blueprint_fallback(
    *,
    session_id: str | None,
    topic: str,
    final_solution: str,
    dispatch_state: dict[str, Any] | None,
    warning: str,
) -> AgentSystemBlueprint:
    dispatch = dispatch_state or {}
    selected_agents = dispatch.get("selected_agents") or []
    agents = [
        BlueprintAgentSpec(
            name=name,
            role="讨论参与者",
            goal=f"参与讨论：{dispatch.get('refined_topic') or topic}",
            instructions="使用会话讨论和最终方案作为素材",
            outputs=["Agent 系统推荐方案"],
        )
        for name in selected_agents
    ]
    if not agents:
        agents = [
            BlueprintAgentSpec(
                name="生成器",
                role="蓝图生成器",
                goal="将讨论结果转化为可复用的 agent 系统设计",
                outputs=["Agent 系统蓝图"],
            )
        ]
    return AgentSystemBlueprint(
        session_id=session_id,
        name="本次讨论总览",
        problem_statement=dispatch.get("refined_topic") or topic,
        target_user="Agent 系统构建者",
        use_cases=[dispatch.get("expected_final_output") or "生成可复用的 agent 系统蓝图"],
        non_goals=["生成可运行的框架项目"],
        output_contract=OutputContract(
            description=_limit_text(final_solution, max_chars=500) or "未生成结论",
            format="markdown",
            required_sections=["problem", "agents", "workflow", "evaluation"],
        ),
        workflow=WorkflowSpec(
            steps=[
                WorkflowStep(
                    id="step_1",
                    name="生成蓝图",
                    owner_agent=agents[0].name,
                    input="用户想法、派发状态、讨论记录、最终方案",
                    output="Agent 系统蓝图",
                    next=[],
                    error_path="返回带提醒的确定性备用方案",
                )
            ]
        ),
        agents=agents,
        evaluation=EvaluationSpec(
            criteria=[
                "蓝图包含参与者、工作流、输入契约、输出契约和评估标准"
            ],
            test_cases=["根据原始想法，用户能识别每个步骤由哪个 agent 负责"],
        ),
        risks=[
            RiskSpec(risk="备用蓝图可能不如模型输出具体", mitigation="展示提醒信息")
        ],
        generation=GenerationMeta(source="deterministic_fallback", warnings=[warning]),
    )


def _limit_text(value: str, *, max_chars: int) -> str:
    text = strip_hidden_reasoning(value or "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED]"


def build_blueprint_prompt(
    *,
    topic: str,
    final_solution: str,
    dispatch_state: dict[str, Any] | None,
    discussion_transcript: str,
) -> str:
    dispatch_json = json.dumps(dispatch_state or {}, ensure_ascii=False)
    return f"""用中文生成一份 Agent System Blueprint，严格输出 JSON。

规则：
- 只输出 JSON，不要 markdown 代码块。
- 所有名称、描述、角色、目标等文本必须用中文。
- 不含  thinking 标签或隐藏推理。
- JSON 须符合 AgentSystemBlueprint schema。

Original or refined topic:
{_limit_text(topic, max_chars=4000)}

Dispatch state:
{_limit_text(dispatch_json, max_chars=6000)}

Final solution:
{_limit_text(final_solution, max_chars=10000)}

Discussion transcript:
{_limit_text(discussion_transcript, max_chars=12000)}

Required top-level keys:
schema_version, id, session_id, name, status, problem_statement, target_user,
use_cases, non_goals, input_contract, output_contract, workflow, agents, tools,
evaluation, risks, exports, generation
"""


async def generate_blueprint(
    *,
    service: Any,
    session_id: str | None,
    topic: str,
    final_solution: str,
    dispatch_state: dict[str, Any] | None,
    discussion_transcript: str,
) -> BlueprintGenerationResult:
    prompt = build_blueprint_prompt(
        topic=topic,
        final_solution=final_solution,
        dispatch_state=dispatch_state,
        discussion_transcript=discussion_transcript,
    )
    warnings: list[str] = []
    for attempt in range(2):
        content = prompt
        if attempt == 1:
            content += "\nPrevious output was invalid. Return valid JSON only."
        history = ChatHistory()
        history.add_message(ChatMessageContent(role=AuthorRole.USER, content=content))
        try:
            response = await service.get_chat_message_content(
                chat_history=history,
                settings=PromptExecutionSettings(),
            )
            blueprint = parse_blueprint_response(response.content or "", session_id=session_id)
            if attempt == 1:
                blueprint.generation.source = "retry"
                blueprint.generation.warnings = []
            return BlueprintGenerationResult(blueprint=blueprint, warnings=warnings)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            warnings.append(
                f"模型输出格式校验未通过（第{attempt + 1}次）：{type(exc).__name__}: {exc}"
            )
        except Exception as exc:
            warnings.append(f"模型调用异常，已使用备用方案：{type(exc).__name__}: {exc}")
            break

    fallback = build_blueprint_fallback(
        session_id=session_id,
        topic=topic,
        final_solution=final_solution,
        dispatch_state=dispatch_state,
        warning="; ".join(warnings) or "已使用备用方案生成蓝图",
    )
    return BlueprintGenerationResult(blueprint=fallback, warnings=fallback.generation.warnings)
