import json
from typing import Any, Literal, NotRequired, Required, TypedDict

from langgraph.graph import END, StateGraph

from llm.qwen_client import LocalQwen
from schemas.model_error_schema import (
    ErrorGovernanceReport,
    ErrorGroup,
    GovernanceIntent,
    ModelErrorSnapshot,
    RepairPlan,
)
from tools.model_error_tools import (
    analyze_model_errors,
    group_model_errors,
    load_model_error_snapshot,
    parse_governance_intent,
)


class ModelErrorAgentState(TypedDict, total=False):
    user_message: Required[str]
    decision_model: NotRequired[Any]
    snapshot: NotRequired[ModelErrorSnapshot]
    intent: NotRequired[GovernanceIntent]
    groups: NotRequired[list[ErrorGroup]]
    repair_plan: NotRequired[RepairPlan | None]
    decision_source: NotRequired[str]
    report: NotRequired[ErrorGovernanceReport]


governance_llm = LocalQwen()


def collect_error_snapshot(state: ModelErrorAgentState) -> dict:
    return {
        "snapshot": load_model_error_snapshot(),
        "intent": parse_governance_intent(state["user_message"]),
    }


def group_root_causes(state: ModelErrorAgentState) -> dict:
    return {
        "groups": group_model_errors(state["snapshot"], state["intent"]),
    }


def _build_decision_prompt(state: ModelErrorAgentState) -> str:
    snapshot = state["snapshot"]
    intent = state["intent"]
    payload = {
        "project_id": snapshot.project_id,
        "project_revision": snapshot.project_revision,
        "intent": intent.model_dump(),
        "groups": [
            {
                "group_id": group.group_id,
                "root_cause_code": group.root_cause_code,
                "root_object_ids": group.root_object_ids,
                "affected_object_ids": [item.object_id for item in group.objects],
                "candidate": (
                    group.candidate.model_dump() if group.candidate else None
                ),
                "allowed_routes": group.allowed_routes,
            }
            for group in state["groups"]
        ],
    }
    return f"""
你是船舶 CAD 全船模型错误治理 Agent 的受控决策节点。

只能依据输入中的结构化事实，为每个问题组选择一条处置路线。
每个 route 必须属于该组 allowed_routes。
只能引用输入中已有的 group_id 和 candidate_id。
不得生成边界、定位面、对象 ID 或几何候选。
update_panel 不得选择 auto_execute。
当 low_risk_policy=require_confirmation 时不得选择 auto_execute。
当 mode=analyze_only 时不得选择 auto_execute。
confirm_then_execute 的 requires_confirmation 必须为 true，其他路线必须为 false。
observation 只写一句简短观察，evidence 最多五条且只引用给定事实。

只返回 JSON，不要 Markdown。结构如下：
{{
  "project_id": "输入中的工程ID",
  "expected_project_revision": "输入中的工程版本",
  "intent": {{
    "mode": "analyze_only | execute_allowed",
    "low_risk_policy": "allow_auto_execute | require_confirmation"
  }},
  "decisions": [
    {{
      "group_id": "输入中的问题组ID",
      "route": "该组 allowed_routes 中的一项",
      "candidate_id": "输入候选ID或null",
      "reason_code": "简短大写原因码",
      "observation": "一句观察",
      "evidence": ["最多五条给定事实"],
      "requires_confirmation": false
    }}
  ]
}}

当前状态：
{json.dumps(payload, ensure_ascii=False)}
"""


def decide_repair_routes(state: ModelErrorAgentState) -> dict:
    model = state.get("decision_model") or governance_llm
    try:
        raw = model.invoke(_build_decision_prompt(state))
        plan = RepairPlan.model_validate(json.loads(raw))
        return {"repair_plan": plan, "decision_source": "llm"}
    except Exception:
        return {"repair_plan": None, "decision_source": "fallback"}


def build_governance_report(state: ModelErrorAgentState) -> dict:
    return {
        "report": analyze_model_errors(
            state["user_message"],
            plan=state.get("repair_plan"),
            decision_source=state.get("decision_source", "fallback"),
        )
    }


def route_after_plan(
    state: ModelErrorAgentState,
) -> Literal["report_only", "request_confirmation", "repair_safety_gate"]:
    return state["report"].workflow_next_step


def finish_route(state: ModelErrorAgentState) -> dict:
    return {}


builder = StateGraph(ModelErrorAgentState)
builder.add_node("collect_error_snapshot", collect_error_snapshot)
builder.add_node("group_root_causes", group_root_causes)
builder.add_node("decide_repair_routes", decide_repair_routes)
builder.add_node("build_governance_report", build_governance_report)
builder.add_node("report_only", finish_route)
builder.add_node("request_confirmation", finish_route)
builder.add_node("repair_safety_gate", finish_route)
builder.set_entry_point("collect_error_snapshot")
builder.add_edge("collect_error_snapshot", "group_root_causes")
builder.add_edge("group_root_causes", "decide_repair_routes")
builder.add_edge("decide_repair_routes", "build_governance_report")
builder.add_conditional_edges(
    "build_governance_report",
    route_after_plan,
    {
        "report_only": "report_only",
        "request_confirmation": "request_confirmation",
        "repair_safety_gate": "repair_safety_gate",
    },
)
builder.add_edge("report_only", END)
builder.add_edge("request_confirmation", END)
builder.add_edge("repair_safety_gate", END)

model_error_graph = builder.compile()


def run_model_error_agent(
    user_message: str,
    *,
    decision_model: Any | None = None,
) -> ErrorGovernanceReport:
    state: ModelErrorAgentState = {"user_message": user_message}
    if decision_model is not None:
        state["decision_model"] = decision_model
    result = model_error_graph.invoke(state)
    return result["report"]
