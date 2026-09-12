import json
from typing import Literal

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from agent.state import AgentState
from agent.boundary_session import resolve_boundary_session, recover_missing_scalars
from agent.execution_trace import llm_trace_phase
from llm.qwen_client import LocalQwen, LocalQwenError
from schemas.agent_action_schema import AgentActionPlan
from schemas.agent_decision_schema import (
    AgentDecision,
    AgentDecisionRecord,
    DecisionAction,
    DecisionSource,
)
from schemas.panel_schema import PanelRequest
from schemas.project_context_schema import ObjectMatchResult, ProjectInspectionResult
from tools.design_review_tools import DesignReviewError, review_panel_design
from tools.cad_tools import create_panel
from tools.boundary_tools import mask_boundary_text
from tools.project_context_tools import (
    ProjectContextError,
    extract_demo_reference_query,
    inspect_project_context,
)
from tools.ruler_plane_tools import (
    extract_known_ruler_plane_name,
    normalize_ruler_plane_name,
    reference_plane_is_mentioned,
)


llm = LocalQwen()
MAX_MODEL_RETRIES = 1
MAX_DECISION_STEPS = 2


# =====================
# Node 1
# 调用 LLM 解析需求
# =====================

def parse_structure(state: AgentState) -> dict:
    prompt = f"""
你是船舶 CAD 结构参数抽取助手。

用户需求：
{state['user_input']}

请先判断用户是否明确要求创建板架，再返回合法 JSON，不要解释，也不要使用 Markdown。

如果用户明确要求创建板架，返回：
{{
    "action": "create_panel",
    "panel": {{
        "type": "panel",
        "reference_plane": null,
        "boundaries": [],
        "thickness": null,
        "material": null
    }}
}}

如果用户不是在要求创建板架，例如普通问答、解释材料、创建其他对象或任务不明确，返回：
{{
    "action": "unsupported",
    "panel": null
}}

要求：
1. 只有用户明确表达创建意图时，action 才能是 create_panel。
2. thickness 使用毫米数值。
3. boundaries 固定返回空数组；边界将由程序从用户原文确定性解析，不要提取或补造边界。
4. 已知标尺面范围为：X轴 FR-10 至 FR200、Y轴 SL-40 至 SL40、Z轴 LV-5 至 LV50。
5. 用户使用“第N肋位”或“N号肋位”且 N 在 -10 至 200 范围内时，转换为 FRN，例如“第100肋位”返回 FR100。
6. FR、SL、LV 标尺面统一使用大写前缀并移除前缀与数字之间的空格。
7. 其他工程名称保留原文，不要自行改名；X=10000 等坐标表达式也保留原文。
8. 不得虚构 reference_plane、thickness 或 material，无法确定时填写 null。
9. 多轮补充只修改用户明确修正的字段，保留历史需求中的其他参数。
"""

    retry_count = state.get("retry_count", 0)
    if retry_count:
        prompt += f"""

上一次输出没有通过结构校验，请根据错误修正后重新输出完整 JSON。
上一次输出：
{state.get('llm_raw_output')}
校验错误：
{state.get('error')}
"""

    try:
        with llm_trace_phase("parse"):
            result = llm.invoke(prompt)
    except LocalQwenError as exc:
        return {
            "error": f"本地模型调用失败：{exc}",
            "error_code": exc.error_code,
            "retryable_error": exc.retryable,
            "retry_count": state.get("retry_count", 0) + 1,
            "llm_raw_output": None,
        }
    except Exception as exc:
        return {
            "error": f"本地模型调用失败：{exc}",
            "error_code": "LLM_INTERNAL_ERROR",
            "retryable_error": False,
            "llm_raw_output": None,
        }

    return {
        "llm_raw_output": result,
        "error": None,
        "error_code": None,
        "retryable_error": False,
        "clarification": None,
    }


# =====================
# Node 2
# JSON解析、必填字段与Panel Schema校验
# =====================

def validate_structure(state: AgentState) -> dict:
    if state.get("error"):
        return {}

    raw_output = state.get("llm_raw_output")
    if not raw_output:
        return {
            "error": "模型没有返回板架结构参数。",
        }

    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as exc:
        return _model_output_error(
            state,
            f"模型返回的 JSON 格式不正确：{exc}",
            error_code="LLM_INVALID_JSON",
        )

    if not isinstance(data, dict):
        return _model_output_error(
            state,
            "模型返回的 JSON 必须是对象。",
            error_code="LLM_INVALID_JSON",
        )

    # Boundary authority is the user source, not the model's proposed list.
    if data.get('action') == 'create_panel' and isinstance(data.get('panel'), dict):
        data['panel']['boundaries'] = []
    try:
        action_plan = AgentActionPlan.model_validate(data)
    except ValidationError as exc:
        return _model_output_error(
            state,
            (
                "模型返回的动作计划不合法："
                f"{_format_validation_error(exc)}"
            ),
            error_code="LLM_INVALID_ACTION",
        )

    if action_plan.action == "unsupported":
        return {
            "action_plan": action_plan,
            "structure_json": None,
            "final_response": "当前仅支持创建板架，未执行任何 CAD 操作。",
            "clarification": None,
            "error": None,
            "error_code": None,
            "retryable_error": False,
        }

    data = action_plan.panel.model_dump()
    boundary_result = resolve_boundary_session(state["user_input"])
    data["boundaries"] = [item.model_dump() for item in boundary_result.boundaries]

    reference_text = mask_boundary_text(state["user_input"])
    recover_missing_scalars(data, reference_text)
    reference_plane = data.get("reference_plane")
    # A model must not promote a boundary target to a positioning plane.
    if (
        reference_text != state["user_input"]
        and isinstance(reference_plane, str)
        and not reference_plane_is_mentioned(reference_plane, reference_text)
    ):
        reference_plane = None
        data["reference_plane"] = None
    if isinstance(reference_plane, str) and reference_plane.strip():
        data["reference_plane"] = normalize_ruler_plane_name(
            reference_plane
        )
    else:
        extracted_plane = extract_known_ruler_plane_name(
            reference_text
        )
        if extracted_plane is not None:
            data["reference_plane"] = extracted_plane
        else:
            data["reference_plane"] = extract_demo_reference_query(reference_text)

    missing_fields = _find_missing_required_fields(data)
    if missing_fields or boundary_result.issues:
        prompts = []
        if missing_fields:
            prompts.append(f"创建板架还需要提供：{'、'.join(missing_fields)}。")
        prompts.extend(issue.message for issue in boundary_result.issues)
        return {
            "action_plan": action_plan,
            "structure_json": data,
            "clarification": "；".join(prompts),
            "boundary_result": boundary_result,
            "error": None,
            "error_code": None,
            "retryable_error": False,
        }

    # 已知标尺面只做名称规范化；是否存在和可用仍由 CAD 判断。
    try:
        panel_request = PanelRequest.model_validate(data)
    except ValidationError as exc:
        return {
            "action_plan": action_plan,
            "structure_json": data,
            "error": (
                "板架参数校验失败："
                f"{_format_validation_error(exc)}"
            ),
            "error_code": "PANEL_VALIDATION_ERROR",
            "retryable_error": False,
        }

    return {
        "action_plan": action_plan,
        "structure_json": data,
        "panel_request": panel_request,
        "boundary_result": boundary_result,
        "clarification": None,
        "error": None,
        "error_code": None,
        "retryable_error": False,
    }


def _model_output_error(
    state: AgentState,
    message: str,
    *,
    error_code: str,
) -> dict:
    return {
        "error": message,
        "error_code": error_code,
        "retryable_error": True,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def _find_missing_required_fields(
    data: dict,
) -> list[str]:
    field_labels = {
        "reference_plane": "定位面",
        "thickness": "厚度",
        "material": "材料",
    }
    missing_fields = []

    for field_name, label in field_labels.items():
        value = data.get(field_name)
        if value is None:
            missing_fields.append(label)
        elif isinstance(value, str) and not value.strip():
            missing_fields.append(label)

    return missing_fields

def _format_validation_error(error: ValidationError) -> str:
    messages = []

    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"])
        messages.append(f"{field}: {item['msg']}")

    return "；".join(messages)


# =====================
# Node 3
# 查询前策略决策
# =====================

def decide_before_inspection(state: AgentState) -> dict:
    if state.get("error"):
        decision = AgentDecision(
            next_action="stop",
            reason_code="AGENT_ERROR",
            observation="流程存在未解决错误，不能继续执行。",
            evidence=[state.get("error_code") or "UNKNOWN_ERROR"],
        )
    elif state.get("clarification"):
        decision = AgentDecision(
            next_action="ask_clarification",
            reason_code=_clarification_reason(state),
            observation="创建参数仍不完整或输入需要修正。",
            evidence=_candidate_evidence(state),
            user_message=state["clarification"],
        )
    elif (
        state.get("action_plan") is None
        or state["action_plan"].action != "create_panel"
    ):
        decision = AgentDecision(
            next_action="stop",
            reason_code="UNSUPPORTED_REQUEST",
            observation="当前请求不属于板架创建能力。",
            evidence=["action=unsupported"],
        )
    elif state.get("panel_request") is None:
        decision = AgentDecision(
            next_action="stop",
            reason_code="INVALID_USER_INPUT",
            observation="没有可供工程查询的有效板架请求。",
            evidence=[state.get("error_code") or "PANEL_REQUEST_MISSING"],
        )
    else:
        panel = state["panel_request"]
        decision = AgentDecision(
            next_action="inspect_project_context",
            reason_code="PROJECT_CONTEXT_UNVERIFIED",
            observation="参数格式已通过校验，但定位面和边界尚未查询工程目录。",
            evidence=[
                f"reference_plane={panel.reference_plane}",
                *[
                    f"boundary={item.operator}{item.target}"
                    for item in panel.boundaries[:3]
                ],
            ][:4],
        )
    return _decision_update(state, decision, source="policy")


# =====================
# Node 4
# 只读 Mock 工程查询
# =====================

def inspect_project_context_node(state: AgentState) -> dict:
    panel_request = state.get("panel_request")
    if panel_request is None:
        return {
            "error": "没有通过校验的板架参数，无法查询工程上下文。",
            "error_code": "PROJECT_CONTEXT_INVALID",
            "project_inspection": None,
        }
    try:
        inspection = inspect_project_context(panel_request)
    except ProjectContextError as exc:
        return {
            "error": str(exc),
            "error_code": exc.error_code,
            "project_inspection": None,
        }
    except Exception:
        return {
            "error": "Mock 工程目录查询失败。",
            "error_code": "PROJECT_CONTEXT_LOAD_ERROR",
            "project_inspection": None,
        }
    return {
        "project_inspection": inspection,
        "error": None,
        "error_code": None,
    }


# =====================
# Node 5
# 创建前确定性设计评审
# =====================

def review_panel_design_node(state: AgentState) -> dict:
    panel_request = state.get("panel_request")
    inspection = state.get("project_inspection")
    if panel_request is None or inspection is None:
        return {
            "design_review": None,
            "error": "缺少有效请求或工程查询结果，无法执行创建前评审。",
            "error_code": "DESIGN_REVIEW_INPUT_MISSING",
        }
    try:
        review = review_panel_design(panel_request, inspection)
    except DesignReviewError as exc:
        return {
            "design_review": None,
            "error": str(exc),
            "error_code": exc.error_code,
        }
    except Exception:
        return {
            "design_review": None,
            "error": "板架创建前评审失败。",
            "error_code": "DESIGN_REVIEW_ERROR",
        }
    return {
        "design_review": review,
        "error": None,
        "error_code": None,
    }


# =====================
# Node 6
# 查询后 Agent 决策与安全复核
# =====================

def decide_after_inspection(state: AgentState) -> dict:
    safe_decision = _derive_safe_decision(state)
    source: DecisionSource = "fallback"
    final_decision = safe_decision

    if state.get("decision_count", 0) >= MAX_DECISION_STEPS:
        final_decision = AgentDecision(
            next_action="stop",
            reason_code="DECISION_LIMIT_REACHED",
            observation="Agent 已达到本次请求的最大决策步数。",
            evidence=[f"max_steps={MAX_DECISION_STEPS}"],
        )
    elif state.get("project_inspection") is not None:
        try:
            with llm_trace_phase("decision"):
                raw = llm.invoke(_build_decision_prompt(state))
            parsed = json.loads(raw)
            llm_decision = AgentDecision.model_validate(parsed)
            if llm_decision.next_action == safe_decision.next_action:
                preserve_review_notice = safe_decision.reason_code in {
                    "DESIGN_REVIEW_WARNING",
                    "DESIGN_REVIEW_BLOCKED",
                }
                final_decision = AgentDecision(
                    next_action=llm_decision.next_action,
                    reason_code=safe_decision.reason_code,
                    observation=(
                        safe_decision.observation
                        if preserve_review_notice
                        else llm_decision.observation
                    ),
                    evidence=(
                        safe_decision.evidence
                        if preserve_review_notice
                        else llm_decision.evidence or safe_decision.evidence
                    ),
                    user_message=(
                        llm_decision.user_message
                        if llm_decision.next_action == "ask_clarification"
                        else None
                    ),
                )
                source = "llm"
            else:
                source = "safety_override"
        except Exception:
            final_decision = safe_decision
            source = "fallback"

    update = _decision_update(state, final_decision, source=source)
    if final_decision.next_action == "ask_clarification":
        update.update({
            "clarification": final_decision.user_message,
            "error": None,
            "error_code": None,
        })
    elif final_decision.next_action == "stop" and not state.get("error"):
        update.update({
            "error": final_decision.observation,
            "error_code": _decision_error_code(final_decision),
        })
    return update


# =====================
# Node 7
# 确定性 CAD 安全门禁
# =====================

def safety_gate(state: AgentState) -> dict:
    decision = state.get("decision")
    inspection = state.get("project_inspection")
    authorized = (
        state.get("action_plan") is not None
        and state["action_plan"].action == "create_panel"
        and state.get("panel_request") is not None
        and inspection is not None
        and inspection.all_resolved()
        and decision is not None
        and decision.next_action == "prepare_creation"
        and state.get("decision_count", 0) <= MAX_DECISION_STEPS
    )
    if authorized:
        return {
            "execution_authorized": True,
            "authorization_reason": "EXECUTION_PREFLIGHT_PASSED",
            "error": None,
            "error_code": None,
        }
    reason = "PROJECT_OBJECT_NOT_RESOLVED"
    return {
        "execution_authorized": False,
        "authorization_reason": reason,
        "error": "Agent 安全门禁拒绝了板架创建请求。",
        "error_code": "AGENT_SAFETY_GATE_REJECTED",
    }


# =====================
# Node 8
# CAD创建
# =====================

def execute_cad(state: AgentState) -> dict:
    if state.get("execution_authorized") is not True:
        return {
            "error": "板架创建请求尚未通过 Agent 安全门禁。",
            "error_code": "AGENT_SAFETY_GATE_REJECTED",
        }
    panel_request = state.get("panel_request")
    if panel_request is None:
        return {
            "error": "没有通过校验的板架参数，无法执行。",
        }

    result = create_panel(panel_request)

    return {
        "cad_result": result,
        "error": None if result.success else result.message,
        "error_code": None if result.success else result.error_code,
    }


# =====================
# Conditional routing
# =====================

def route_after_validation(
    state: AgentState,
) -> Literal["retry_parse", "decide", "finish"]:
    if (
        state.get("retryable_error")
        and state.get("retry_count", 0) <= MAX_MODEL_RETRIES
    ):
        return "retry_parse"

    return "decide"


def route_after_initial_decision(
    state: AgentState,
) -> Literal["inspect", "finish"]:
    decision = state.get("decision")
    if (
        decision is not None
        and decision.next_action == "inspect_project_context"
        and state.get("panel_request") is not None
    ):
        return "inspect"
    return "finish"


def route_after_project_inspection(
    state: AgentState,
) -> Literal["decide"]:
    return "decide"


def route_after_inspection_decision(
    state: AgentState,
) -> Literal["authorize", "finish"]:
    decision = state.get("decision")
    if decision is not None and decision.next_action == "prepare_creation":
        return "authorize"
    return "finish"


def route_after_safety_gate(
    state: AgentState,
) -> Literal["cad", "finish"]:
    return "cad" if state.get("execution_authorized") is True else "finish"


def _decision_update(
    state: AgentState,
    decision: AgentDecision,
    *,
    source: DecisionSource,
) -> dict:
    history = list(state.get("decision_history", []))
    sequence = len(history) + 1
    history.append(
        AgentDecisionRecord(
            sequence=sequence,
            source=source,
            decision=decision,
        )
    )
    return {
        "decision": decision,
        "decision_history": history,
        "decision_count": sequence,
    }


def _clarification_reason(state: AgentState) -> Literal[
    "MISSING_REQUIRED_FIELD", "INVALID_USER_INPUT"
]:
    boundary_result = state.get("boundary_result")
    if boundary_result is not None and boundary_result.issues:
        return "INVALID_USER_INPUT"
    return "MISSING_REQUIRED_FIELD"


def _candidate_evidence(state: AgentState) -> list[str]:
    data = state.get("structure_json")
    if not isinstance(data, dict):
        return []
    evidence = []
    for name in ("reference_plane", "thickness", "material"):
        value = data.get(name)
        evidence.append(f"{name}={value if value not in (None, '') else 'missing'}")
    boundaries = data.get("boundaries")
    evidence.append(f"boundary_count={len(boundaries) if isinstance(boundaries, list) else 0}")
    return evidence[:4]


def _derive_safe_decision(state: AgentState) -> AgentDecision:
    if state.get("error"):
        return AgentDecision(
            next_action="stop",
            reason_code="AGENT_ERROR",
            observation=state["error"],
            evidence=[state.get("error_code") or "UNKNOWN_ERROR"],
        )
    inspection = state.get("project_inspection")
    if inspection is None:
        return AgentDecision(
            next_action="stop",
            reason_code="AGENT_ERROR",
            observation="没有获得 Mock 工程查询结果，无法继续创建。",
            evidence=["project_inspection=missing"],
        )

    problem = _first_inspection_problem(inspection)
    if problem is None:
        return AgentDecision(
            next_action="prepare_creation",
            reason_code="ALL_PRECONDITIONS_SATISFIED",
            observation="定位面和全部边界均已在 Mock 工程目录中唯一匹配。",
            evidence=[
                f"{inspection.reference_plane.query}=resolved",
                *[f"{item.query}=resolved" for item in inspection.boundaries[:3]],
            ][:4],
        )

    result, role = problem
    if result.status == "ambiguous":
        reason = "REFERENCE_AMBIGUOUS" if role == "reference_plane" else "BOUNDARY_AMBIGUOUS"
        label = "定位面" if role == "reference_plane" else "边界"
        message = f"{label}“{result.query}”匹配到多个 Mock 工程对象，请选择：{'、'.join(result.candidates)}。"
        return AgentDecision(
            next_action="ask_clarification",
            reason_code=reason,
            observation=f"{label}存在多个候选，不能自动选择。",
            evidence=[f"query={result.query}", *result.candidates[:3]][:4],
            user_message=message,
        )
    if result.status == "not_found":
        reason = "REFERENCE_NOT_FOUND" if role == "reference_plane" else "BOUNDARY_NOT_FOUND"
        label = "定位面" if role == "reference_plane" else "边界"
        return AgentDecision(
            next_action="ask_clarification",
            reason_code=reason,
            observation=f"Mock 工程目录中没有找到{label}“{result.query}”。",
            evidence=[f"query={result.query}", "status=not_found"],
            user_message=f"当前 Mock 工程目录中不存在{label}“{result.query}”，请提供其他对象名称。",
        )
    if result.status == "not_eligible":
        return AgentDecision(
            next_action="stop",
            reason_code="OBJECT_NOT_ELIGIBLE",
            observation=f"对象“{result.query}”不能作为{_role_label(role)}使用。",
            evidence=[f"query={result.query}", f"role={role}"],
        )
    return AgentDecision(
        next_action="stop",
        reason_code="OBJECT_UNAVAILABLE",
        observation=f"对象“{result.query}”在 Mock 工程中不可用。",
        evidence=[f"query={result.query}", "status=unavailable"],
    )


def _first_inspection_problem(
    inspection: ProjectInspectionResult,
) -> tuple[ObjectMatchResult, Literal["reference_plane", "boundary"]] | None:
    if inspection.reference_plane.status != "resolved":
        return inspection.reference_plane, "reference_plane"
    for item in inspection.boundaries:
        if item.status != "resolved":
            return item, "boundary"
    return None


def _role_label(role: str) -> str:
    return "定位面" if role == "reference_plane" else "边界"


def _build_decision_prompt(state: AgentState) -> str:
    panel = state.get("panel_request")
    inspection = state.get("project_inspection")
    payload = {
        "panel_candidate": panel.model_dump() if panel is not None else None,
        "input_issues": [],
        "project_inspection": (
            inspection.model_dump() if inspection is not None else None
        ),
    }
    return f"""
你是船舶 CAD 板架创建 Agent 的决策节点。只能依据给定的结构化状态选择下一步。

允许动作：
- prepare_creation：定位面和全部边界均为 resolved。
- ask_clarification：存在 not_found 或 ambiguous，用户可以补充或选择。
- stop：存在 unavailable、not_eligible 或无法安全继续的状态。

禁止声明未查询对象存在，不得忽略异常匹配状态，不得修改边界比较符，
不得修改用户明确给出的板厚或材料，
不得声称 CCS、强度、真实几何或真实 CAD 已验证或已创建。

仅返回 JSON，不要 Markdown：
{{
  "next_action": "prepare_creation | ask_clarification | stop",
  "reason_code": "从允许原因码中选择",
  "observation": "一句简短观察",
  "evidence": ["最多四条给定事实"],
  "user_message": null
}}

允许原因码：REFERENCE_NOT_FOUND、REFERENCE_AMBIGUOUS、BOUNDARY_NOT_FOUND、
BOUNDARY_AMBIGUOUS、OBJECT_UNAVAILABLE、OBJECT_NOT_ELIGIBLE、
ALL_PRECONDITIONS_SATISFIED。

当前状态：
{json.dumps(payload, ensure_ascii=False)}
"""


def _decision_error_code(decision: AgentDecision) -> str:
    mapping = {
        "OBJECT_UNAVAILABLE": "PROJECT_OBJECT_UNAVAILABLE",
        "OBJECT_NOT_ELIGIBLE": "PROJECT_OBJECT_NOT_ELIGIBLE",
        "DECISION_LIMIT_REACHED": "AGENT_DECISION_LIMIT_REACHED",
        "DESIGN_REVIEW_BLOCKED": "DESIGN_REVIEW_BLOCKED",
    }
    return mapping.get(decision.reason_code, "AGENT_DECISION_STOPPED")


# =====================
# Build Graph
# =====================

builder = StateGraph(AgentState)

builder.add_node("parse", parse_structure)
builder.add_node("validate", validate_structure)
builder.add_node("decide_before_inspection", decide_before_inspection)
builder.add_node("inspect_project_context", inspect_project_context_node)
builder.add_node("decide_after_inspection", decide_after_inspection)
builder.add_node("safety_gate", safety_gate)
builder.add_node("cad", execute_cad)

builder.set_entry_point("parse")
builder.add_edge("parse", "validate")
builder.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "retry_parse": "parse",
        "decide": "decide_before_inspection",
        "finish": END,
    },
)
builder.add_conditional_edges(
    "decide_before_inspection",
    route_after_initial_decision,
    {"inspect": "inspect_project_context", "finish": END},
)
builder.add_conditional_edges(
    "inspect_project_context",
    route_after_project_inspection,
    {"decide": "decide_after_inspection"},
)
builder.add_conditional_edges(
    "decide_after_inspection",
    route_after_inspection_decision,
    {"authorize": "safety_gate", "finish": END},
)
builder.add_conditional_edges(
    "safety_gate",
    route_after_safety_gate,
    {"cad": "cad", "finish": END},
)
builder.add_edge("cad", END)

graph = builder.compile()
