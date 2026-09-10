import json
from typing import Literal

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from agent.state import AgentState
from agent.boundary_session import resolve_boundary_session, recover_missing_scalars
from llm.qwen_client import LocalQwen, LocalQwenError
from schemas.agent_action_schema import AgentActionPlan
from schemas.panel_schema import PanelRequest
from tools.cad_tools import create_panel
from tools.boundary_tools import mask_boundary_text
from tools.ruler_plane_tools import (
    extract_known_ruler_plane_name,
    normalize_ruler_plane_name,
    reference_plane_is_mentioned,
)


llm = LocalQwen()
MAX_MODEL_RETRIES = 1


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
# CAD创建
# =====================

def execute_cad(state: AgentState) -> dict:
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
) -> Literal["retry_parse", "cad", "finish"]:
    if (
        state.get("retryable_error")
        and state.get("retry_count", 0) <= MAX_MODEL_RETRIES
    ):
        return "retry_parse"

    if state.get("error"):
        return "finish"

    if state.get("clarification"):
        return "finish"

    action_plan = state.get("action_plan")
    if action_plan is None or action_plan.action != "create_panel":
        return "finish"

    return "cad" if state.get("panel_request") is not None else "finish"


# =====================
# Build Graph
# =====================

builder = StateGraph(AgentState)

builder.add_node("parse", parse_structure)
builder.add_node("validate", validate_structure)
builder.add_node("cad", execute_cad)

builder.set_entry_point("parse")
builder.add_edge("parse", "validate")
builder.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "retry_parse": "parse",
        "cad": "cad",
        "finish": END,
    },
)
builder.add_edge("cad", END)

graph = builder.compile()
