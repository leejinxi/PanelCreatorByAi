import json
from typing import Literal

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from agent.state import AgentState
from llm.qwen_client import LocalQwen
from schemas.panel_schema import PanelRequest
from tools.cad_tools import create_panel


llm = LocalQwen()


# =====================
# Node 1
# 调用 LLM 解析需求
# =====================

def parse_structure(state: AgentState) -> dict:
    prompt = f"""
你是船舶 CAD 结构设计助手。

用户需求：
{state['user_input']}

请解析为板架创建参数，只返回合法 JSON，不要解释，也不要使用 Markdown：
{{
    "type": "panel",
    "reference_plane": "",
    "boundaries": {{
        "top": null,
        "bottom": null,
        "left": null,
        "right": null
    }},
    "thickness": 0,
    "material": ""
}}

要求：
1. thickness 使用毫米数值。
2. 无法确定的边界填写 null。
3. 不得虚构 reference_plane、thickness 或 material。
4. 无法确定的必填字符串填写空字符串。
5. 无法确定 thickness 时填写 0。
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
# JSON解析与Schema校验
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

    missing_fields = _find_missing_required_fields(data)
    if missing_fields:
        return {
            "structure_json": data,
            "clarification": (
                "创建板架还需要提供："
                f"{'、'.join(missing_fields)}。"
            ),
            "error": None,
        }

    try:
        panel_request = PanelRequest.model_validate(data)
    except ValidationError as exc:
        return {
            "structure_json": data,
            "error": (
                "板架参数校验失败："
                f"{_format_validation_error(exc)}"
            ),
        }

    return {
        "structure_json": data,
        "panel_request": panel_request,
        "clarification": None,
        "error": None,
    }


def _find_missing_required_fields(data: dict) -> list[str]:
    field_labels = {
        "reference_plane": "基准面",
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
            "error": "没有通过校验的板架参数，无法执行 CAD。",
        }

    try:
        result = create_panel(
            reference_plane=panel_request.reference_plane,
            boundaries=panel_request.boundaries.model_dump(),
            thickness=panel_request.thickness,
            material=panel_request.material,
        )
    except Exception as exc:
        return {
            "error": f"CAD 创建板架失败：{exc}",
        }

    return {
        "cad_result": result,
        "error": None,
    }


# =====================
# Conditional routing
# =====================

def route_after_validation(
    state: AgentState,
) -> Literal["cad", "finish"]:
    if state.get("error"):
        return "finish"

    if state.get("clarification"):
        return "finish"

    if state.get("panel_request") is None:
        return "finish"

    return "cad"


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
        "cad": "cad",
        "finish": END,
    },
)
builder.add_edge("cad", END)

graph = builder.compile()
