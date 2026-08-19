import json
from typing import Literal

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from agent.state import AgentState
from llm.qwen_client import LocalQwen
from schemas.agent_action_schema import AgentActionPlan
from schemas.panel_schema import PanelRequest
from tools.cad_tools import create_panel
from tools.reference_plane_tools import (
    list_reference_planes,
    resolve_reference_plane,
)


llm = LocalQwen()


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
        "boundaries": {{
            "top": null,
            "bottom": null,
            "left": null,
            "right": null
        }},
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
3. 无法确定的边界填写 null。
4. reference_plane 可以是 FR100、SURFACE_20、主甲板中心面等任意工程名称。
5. 用户明确提供的定位面原文必须完整复制到 reference_plane，不要自行改名。
6. 如果用户使用 X=10000 等坐标定位，也保留原始表达式到 reference_plane。
7. 不得虚构 reference_plane、thickness 或 material，无法确定时填写 null。
"""

    try:
        result = llm.invoke(prompt)
    except Exception as exc:
        return {
            "error": f"本地模型调用失败：{exc}",
            "llm_raw_output": None,
        }

    return {
        "llm_raw_output": result,
        "error": None,
        "clarification": None,
    }


# =====================
# Node 2
# JSON解析与基础字段校验
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
        return {
            "error": f"模型返回的 JSON 格式不正确：{exc}",
        }

    if not isinstance(data, dict):
        return {
            "error": "模型返回的 JSON 必须是对象。",
        }

    try:
        action_plan = AgentActionPlan.model_validate(data)
    except ValidationError as exc:
        return {
            "error": (
                "模型返回的动作计划不合法："
                f"{_format_validation_error(exc)}"
            ),
        }

    if action_plan.action == "unsupported":
        return {
            "action_plan": action_plan,
            "structure_json": None,
            "final_response": "当前仅支持创建板架，未执行任何 CAD 操作。",
            "clarification": None,
            "error": None,
        }

    data = action_plan.panel.model_dump()

    # 定位面可能被小模型漏提取，后续 resolve_plane 会直接从用户原文和
    # 当前工程目录中做确定性解析，因此这里仅拦截其他必填参数。
    missing_fields = _find_missing_required_fields(
        data,
        include_reference_plane=False,
    )
    if missing_fields:
        return {
            "action_plan": action_plan,
            "structure_json": data,
            "clarification": (
                "创建板架还需要提供："
                f"{'、'.join(missing_fields)}。"
            ),
            "error": None,
        }

    return {
        "action_plan": action_plan,
        "structure_json": data,
        "clarification": None,
        "error": None,
    }


def _find_missing_required_fields(
    data: dict,
    *,
    include_reference_plane: bool = True,
) -> list[str]:
    field_labels = {
        "thickness": "厚度",
        "material": "材料",
    }
    if include_reference_plane:
        field_labels = {
            "reference_plane": "定位面",
            **field_labels,
        }
    missing_fields = []

    for field_name, label in field_labels.items():
        value = data.get(field_name)
        if value is None:
            missing_fields.append(label)
        elif isinstance(value, str) and not value.strip():
            missing_fields.append(label)

    return missing_fields


# =====================
# Node 3
# 当前工程定位面解析
# =====================

def resolve_plane(state: AgentState) -> dict:
    if state.get("error") or state.get("clarification"):
        return {}

    data = state.get("structure_json")
    if not data:
        return {
            "error": "没有可用于定位面解析的板架参数。",
        }

    llm_reference = data.get("reference_plane")
    if not isinstance(llm_reference, str):
        llm_reference = None

    planes = list_reference_planes()
    resolution = resolve_reference_plane(
        user_input=state["user_input"],
        planes=planes,
        llm_reference=llm_reference,
    )

    if resolution.status != "resolved" or resolution.resolved is None:
        candidate_names = [
            plane.name
            for plane in resolution.candidates
        ]
        candidate_text = (
            f" 候选项：{'、'.join(candidate_names)}。"
            if candidate_names
            else ""
        )
        return {
            "reference_plane_resolution": resolution,
            "clarification": (
                f"{resolution.message or '无法确定定位面。'}"
                f"{candidate_text}"
            ),
            "error": None,
        }

    resolved_data = {
        **data,
        "reference_plane": resolution.resolved.name,
    }

    try:
        panel_request = PanelRequest.model_validate(resolved_data)
    except ValidationError as exc:
        return {
            "structure_json": resolved_data,
            "reference_plane_resolution": resolution,
            "error": (
                "板架参数校验失败："
                f"{_format_validation_error(exc)}"
            ),
        }

    return {
        "structure_json": resolved_data,
        "reference_plane_resolution": resolution,
        "panel_request": panel_request,
        "clarification": None,
        "error": None,
    }


def _format_validation_error(error: ValidationError) -> str:
    messages = []

    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"])
        messages.append(f"{field}: {item['msg']}")

    return "；".join(messages)


# =====================
# Node 4
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
    }


# =====================
# Conditional routing
# =====================

def route_after_validation(
    state: AgentState,
) -> Literal["resolve_plane", "finish"]:
    if state.get("error"):
        return "finish"

    if state.get("clarification"):
        return "finish"

    action_plan = state.get("action_plan")
    if action_plan is None or action_plan.action != "create_panel":
        return "finish"

    return "resolve_plane"


def route_after_plane_resolution(
    state: AgentState,
) -> Literal["cad", "finish"]:
    if state.get("error") or state.get("clarification"):
        return "finish"

    return "cad" if state.get("panel_request") is not None else "finish"


# =====================
# Build Graph
# =====================

builder = StateGraph(AgentState)

builder.add_node("parse", parse_structure)
builder.add_node("validate", validate_structure)
builder.add_node("resolve_plane", resolve_plane)
builder.add_node("cad", execute_cad)

builder.set_entry_point("parse")
builder.add_edge("parse", "validate")
builder.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "resolve_plane": "resolve_plane",
        "finish": END,
    },
)
builder.add_conditional_edges(
    "resolve_plane",
    route_after_plane_resolution,
    {
        "cad": "cad",
        "finish": END,
    },
)
builder.add_edge("cad", END)

graph = builder.compile()
