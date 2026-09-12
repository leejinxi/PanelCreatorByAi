from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from schemas.panel_schema import CadExecutionResult, PanelRequest
from webapp.schemas import (
    AgentRunResponse,
    AgentRunStatus,
    AgentStepView,
    CadResultView,
    DecisionStepView,
    ExecutionMode,
    ExecutionTraceView,
    McpCallView,
    McpResponseView,
    ObjectMatchView,
    PanelView,
    ProjectInspectionView,
    SafetyGateView,
    TraceNodeView,
)


def map_agent_state(
    state: Mapping[str, Any],
    *,
    request_id: str,
    mode: ExecutionMode = "mock",
    trace: Mapping[str, Any] | None = None,
) -> AgentRunResponse:
    """把内部 AgentState 映射为稳定、可公开给页面的响应。"""

    panel = _map_panel(state)
    cad_result = _map_cad_result(state.get("cad_result"))
    if cad_result is not None and cad_result.success and mode in {"mock", "mcp"}:
        cad_result.message = (
            "模拟 CAD 已完成板架创建。" if mode == "mock"
            else "MCP Contract Mock 已完成板架模拟创建，未修改真实 CAD 工程。"
        )
    status, message, error_code = _classify_result(state, cad_result, mode)

    return AgentRunResponse(
        request_id=request_id,
        status=status,
        mode=mode,
        message=message,
        steps=_build_steps(state, status, cad_result),
        panel=panel,
        cad_result=cad_result,
        error_code=error_code,
        execution_trace=_build_execution_trace(
            state,
            status=status,
            cad_result=cad_result,
            mode=mode,
            trace=trace or {},
        ),
    )


def _map_panel(state: Mapping[str, Any]) -> PanelView | None:
    panel_request = state.get("panel_request")
    if isinstance(panel_request, PanelRequest):
        data = panel_request.model_dump()
    else:
        structure_json = state.get("structure_json")
        if not isinstance(structure_json, Mapping):
            return None
        data = dict(structure_json)

    boundaries = data.get("boundaries")
    if hasattr(boundaries, "model_dump"):
        boundaries = boundaries.model_dump()
    if not isinstance(boundaries, list):
        boundaries = []

    try:
        return PanelView(
            reference_name=_optional_text(data.get("reference_plane")),
            thickness_mm=data.get("thickness"),
            material=_optional_text(data.get("material")),
            boundaries=boundaries,
            boundary_issues=getattr(state.get('boundary_result'), 'issues', []),
        )
    except ValidationError:
        return None


def _map_cad_result(value: Any) -> CadResultView | None:
    if isinstance(value, CadExecutionResult):
        result = value
    elif isinstance(value, Mapping):
        try:
            result = CadExecutionResult.model_validate(value)
        except ValidationError:
            return None
    else:
        return None

    return CadResultView.model_validate(result.model_dump())


def _classify_result(
    state: Mapping[str, Any],
    cad_result: CadResultView | None,
    mode: ExecutionMode,
) -> tuple[AgentRunStatus, str, str | None]:
    if cad_result is not None:
        if cad_result.success:
            message = cad_result.message
            return "success", message, None
        return "error", cad_result.message, cad_result.error_code

    error = _optional_text(state.get("error"))
    if error is not None:
        error_code = (
            _optional_text(state.get("error_code"))
            or "AGENT_EXECUTION_ERROR"
        )
        return "error", error, error_code

    clarification = _optional_text(state.get("clarification"))
    if clarification is not None:
        return "clarification", clarification, None

    final_response = _optional_text(state.get("final_response"))
    if final_response is not None:
        return "unsupported", final_response, None

    return (
        "error",
        "Agent 流程已结束，但没有返回可用结果。",
        "AGENT_EMPTY_RESULT",
    )


def _build_steps(
    state: Mapping[str, Any],
    status: AgentRunStatus,
    cad_result: CadResultView | None,
) -> list[AgentStepView]:
    decision_count = len(state.get("decision_history", []) or [])
    inspected = state.get("project_inspection") is not None
    authorized = state.get("execution_authorized") is True

    if cad_result is not None:
        return [
            AgentStepView(name="parse", status="success"),
            AgentStepView(
                name="decision",
                status="success" if decision_count else "skipped",
            ),
            AgentStepView(
                name="inspect",
                status="success" if inspected else "skipped",
            ),
            AgentStepView(
                name="evaluate",
                status="success" if decision_count > 1 else "skipped",
            ),
            AgentStepView(name="validate", status="success"),
            AgentStepView(
                name="cad",
                status="success" if cad_result.success else "error",
            ),
        ]

    if status == "clarification":
        return [
            AgentStepView(name="parse", status="success"),
            AgentStepView(
                name="decision",
                status="success" if inspected else "attention",
            ),
            AgentStepView(
                name="inspect",
                status="success" if inspected else "skipped",
            ),
            AgentStepView(
                name="evaluate",
                status="attention" if inspected else "skipped",
            ),
            AgentStepView(
                name="validate",
                status="skipped" if inspected else "attention",
            ),
            AgentStepView(name="cad", status="skipped"),
        ]

    if status == "unsupported":
        return [
            AgentStepView(name="parse", status="success"),
            AgentStepView(
                name="decision",
                status="success" if decision_count else "skipped",
            ),
            AgentStepView(name="inspect", status="skipped"),
            AgentStepView(name="evaluate", status="skipped"),
            AgentStepView(name="validate", status="skipped"),
            AgentStepView(name="cad", status="skipped"),
        ]

    error_code = _optional_text(state.get("error_code"))
    has_parsed_output = any(
        state.get(field) is not None
        for field in (
            "llm_raw_output",
            "action_plan",
            "structure_json",
            "panel_request",
        )
    )
    parse_failed = (
        not has_parsed_output
        or error_code is None
        or error_code.startswith("LLM_")
    )
    return [
        AgentStepView(
            name="parse",
            status="error" if parse_failed else "success",
        ),
        AgentStepView(
            name="decision",
            status=(
                "skipped" if parse_failed
                else "error" if not inspected
                else "success"
            ),
        ),
        AgentStepView(
            name="inspect",
            status="success" if inspected else "skipped",
        ),
        AgentStepView(
            name="evaluate",
            status="error" if inspected else "skipped",
        ),
        AgentStepView(
            name="validate",
            status="error" if authorized else "skipped",
        ),
        AgentStepView(name="cad", status="skipped"),
    ]


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None

def _build_execution_trace(
    state: Mapping[str, Any],
    *,
    status: AgentRunStatus,
    cad_result: CadResultView | None,
    mode: ExecutionMode,
    trace: Mapping[str, Any],
) -> ExecutionTraceView:
    """根据实际状态和传输层摘要生成页面 Trace。"""

    error_code = _optional_text(state.get("error_code"))
    has_parsed = any(
        state.get(key) is not None
        for key in ("llm_raw_output", "action_plan", "structure_json", "panel_request")
    )
    llm_status = "error" if error_code and error_code.startswith("LLM_") else (
        "success" if has_parsed or status == "unsupported" else "error"
    )

    mcp_request_data = trace.get("mcp_request")
    mcp_response_data = trace.get("mcp_response")
    mcp_request = (
        McpCallView.model_validate(mcp_request_data)
        if isinstance(mcp_request_data, Mapping)
        else None
    )
    mcp_response = None
    if isinstance(mcp_response_data, Mapping) and isinstance(
        mcp_response_data.get("success"), bool
    ):
        mcp_response = McpResponseView.model_validate(mcp_response_data)

    if mode == "mcp":
        provider = "contract-mock"
        provider_label = "MCP Contract Mock"
    elif mode == "mock":
        provider = "direct-mock"
        provider_label = "Direct Mock"
    else:
        provider = "unconfigured"
        provider_label = "未配置 Provider"

    if mode == 'mcp' and mcp_request is None:
        provider_status = 'skipped'
        provider_summary = '未调用 CAD Provider'
    elif mode == 'mcp' and mcp_response is None:
        provider_status = 'attention'
        provider_summary = '未确认 Provider 执行结果，请勿自动重复创建'
    elif cad_result is not None:
        provider_status = "success" if cad_result.success else "error"
        provider_summary = (
            "返回模拟对象 ID，未修改真实 CAD"
            if cad_result.success
            else f"模拟执行失败：{cad_result.error_code or 'UNKNOWN'}"
        )
    else:
        provider_status = "skipped"
        provider_summary = "未执行 CAD Provider"

    decisions = _map_decision_steps(state)
    inspection = _map_project_inspection(state)
    gate = _map_safety_gate(state, cad_result)
    initial_decision = decisions[0] if decisions else None
    evaluated_decision = decisions[1] if len(decisions) > 1 else None

    policy_status = (
        "skipped" if initial_decision is None
        else "success" if initial_decision.action == "inspect_project_context"
        else "attention"
    )
    policy_summary = (
        "参数有效，决定先查询工程事实"
        if initial_decision and initial_decision.action == "inspect_project_context"
        else "发现缺参或能力边界，流程不进入工程查询"
        if initial_decision
        else "需求解析未产生可执行决策"
    )

    inspection_status = _inspection_trace_status(inspection)
    inspection_summary = _inspection_trace_summary(inspection)

    if evaluated_decision is None:
        evaluation_status = "skipped"
        evaluation_summary = "未获得工程观察，无需二次模型评估"
    elif evaluated_decision.source == "llm":
        evaluation_status = (
            "success" if evaluated_decision.action == "prepare_creation"
            else "attention" if evaluated_decision.action == "ask_clarification"
            else "error"
        )
        evaluation_summary = (
            f"根据查询结果选择：{_decision_action_label(evaluated_decision.action)}"
        )
    elif evaluated_decision.source == "safety_override":
        evaluation_status = "attention"
        evaluation_summary = "Qwen 建议与工程事实冲突，已由安全规则覆盖"
    else:
        evaluation_status = "attention"
        evaluation_summary = "Qwen 决策不可用，确定性规则已接管"

    if gate.authorized:
        gate_status = "success"
        gate_summary = "全部前置条件通过，已授权 CAD 创建"
    elif inspection is None or (
        evaluated_decision is not None
        and evaluated_decision.action in {"ask_clarification", "stop"}
    ):
        gate_status = "skipped"
        gate_summary = "Agent 已停止或请求澄清，未进入执行授权"
    else:
        gate_status = "error"
        gate_summary = "安全门禁拒绝 CAD 创建"

    nodes = [
        TraceNodeView(
            name="qwen_parse",
            label="Qwen 参数解析",
            status=llm_status,
            duration_ms=_llm_phase_duration(trace, "parse"),
            summary="已生成结构化板架候选参数"
            if llm_status == "success"
            else "未返回可用的板架候选参数",
            details={
                "model": "qwen2.5:7b",
                "phase": "parse",
            },
        ),
        TraceNodeView(
            name="policy_decision",
            label="Agent 首次决策",
            status=policy_status,
            summary=policy_summary,
            details={"source": "policy"},
        ),
        TraceNodeView(
            name="project_context",
            label="Mock 工程查询",
            status=inspection_status,
            summary=inspection_summary,
            details={"data_source": "demo_project.json"},
        ),
        TraceNodeView(
            name="qwen_decision",
            label="Qwen 结果评估",
            status=evaluation_status,
            duration_ms=_llm_phase_duration(trace, "decision"),
            summary=evaluation_summary,
            details={
                "source": evaluated_decision.source if evaluated_decision else None,
                "phase": "decision",
            },
        ),
        TraceNodeView(
            name="safety_gate",
            label="Safety Gate",
            status=gate_status,
            summary=gate_summary,
            details={"authorized": gate.authorized},
        ),
        TraceNodeView(
            name="provider",
            label=provider_label,
            status=provider_status,
            duration_ms=(
                _optional_duration(trace.get("mcp_duration_ms"))
                if mode == "mcp" else None
            ),
            summary=provider_summary,
            details={"simulated": True},
        ),
    ]
    return ExecutionTraceView(
        nodes=nodes,
        decision_steps=decisions,
        project_inspection=inspection,
        safety_gate=gate,
        mcp_request=mcp_request,
        mcp_response=mcp_response,
        provider=provider,
        total_ms=_optional_duration(trace.get("total_ms")),
    )


def _llm_phase_duration(
    trace: Mapping[str, Any],
    phase: str,
) -> int | None:
    calls = trace.get("llm_calls")
    if not isinstance(calls, list):
        return None
    durations = [
        item.get("duration_ms")
        for item in calls
        if isinstance(item, Mapping) and item.get("phase") == phase
    ]
    valid = [
        value for value in durations
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return round(sum(valid)) if valid else None


def _decision_action_label(action: str) -> str:
    return {
        "inspect_project_context": "查询工程上下文",
        "ask_clarification": "请求用户补充",
        "prepare_creation": "准备创建板架",
        "stop": "停止执行",
    }.get(action, action)


def _inspection_trace_status(
    inspection: ProjectInspectionView | None,
) -> str:
    if inspection is None:
        return "skipped"
    statuses = [
        inspection.reference_plane.status,
        *(item.status for item in inspection.boundaries),
    ]
    if all(value == "resolved" for value in statuses):
        return "success"
    if any(value in {"unavailable", "not_eligible"} for value in statuses):
        return "error"
    return "attention"


def _inspection_trace_summary(
    inspection: ProjectInspectionView | None,
) -> str:
    if inspection is None:
        return "未执行只读工程对象查询"
    matches = [inspection.reference_plane, *inspection.boundaries]
    resolved = sum(item.status == "resolved" for item in matches)
    if resolved == len(matches):
        return f"定位面及 {len(inspection.boundaries)} 条边界均唯一匹配"
    problem = next(item for item in matches if item.status != "resolved")
    return f"对象 {problem.query}：{problem.status}，等待后续决策"


def _map_decision_steps(state: Mapping[str, Any]) -> list[DecisionStepView]:
    result = []
    for record in state.get("decision_history", []) or []:
        try:
            data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
            decision = data["decision"]
            result.append(DecisionStepView(
                sequence=data["sequence"],
                source=data["source"],
                action=decision["next_action"],
                reason_code=decision["reason_code"],
                observation=decision["observation"],
                evidence=decision.get("evidence", []),
            ))
        except (KeyError, TypeError, ValueError, ValidationError):
            continue
    return result


def _map_project_inspection(
    state: Mapping[str, Any],
) -> ProjectInspectionView | None:
    inspection = state.get("project_inspection")
    if inspection is None:
        return None
    try:
        data = inspection.model_dump() if hasattr(inspection, "model_dump") else dict(inspection)
        return ProjectInspectionView(
            project_name=data["project_name"],
            revision=data["revision"],
            reference_plane=_map_object_match(data["reference_plane"]),
            boundaries=[_map_object_match(item) for item in data.get("boundaries", [])],
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        return None


def _map_object_match(data: Mapping[str, Any]) -> ObjectMatchView:
    return ObjectMatchView(
        query=data["query"],
        role=data["role"],
        status=data["status"],
        resolved_name=data.get("resolved_name"),
        candidates=data.get("candidates", []),
    )


def _map_safety_gate(
    state: Mapping[str, Any],
    cad_result: CadResultView | None,
) -> SafetyGateView:
    value = state.get("execution_authorized")
    authorized = value if isinstance(value, bool) else bool(
        cad_result is not None and cad_result.success
    )
    return SafetyGateView(
        authorized=authorized,
        reason=_optional_text(state.get("authorization_reason")),
    )


def _optional_duration(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, round(value))
