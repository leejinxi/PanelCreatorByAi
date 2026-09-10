from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from schemas.panel_schema import CadExecutionResult, PanelRequest
from webapp.schemas import (
    AgentRunResponse,
    AgentRunStatus,
    AgentStepView,
    CadResultView,
    ExecutionMode,
    ExecutionTraceView,
    McpCallView,
    McpResponseView,
    PanelView,
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
    if cad_result is not None:
        return [
            AgentStepView(name="parse", status="success"),
            AgentStepView(name="validate", status="success"),
            AgentStepView(
                name="cad",
                status="success" if cad_result.success else "error",
            ),
        ]

    if status == "clarification":
        return [
            AgentStepView(name="parse", status="success"),
            AgentStepView(name="validate", status="attention"),
            AgentStepView(name="cad", status="skipped"),
        ]

    if status == "unsupported":
        return [
            AgentStepView(name="parse", status="success"),
            AgentStepView(name="validate", status="success"),
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
            name="validate",
            status="skipped" if parse_failed else "error",
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

    if status == "clarification":
        schema_status = "attention"
        schema_summary = "参数缺失或存在待修正问题，已停止 CAD 调用"
    elif status == "unsupported":
        schema_status = "skipped"
        schema_summary = "当前意图不属于 create_panel"
    elif state.get("panel_request") is not None:
        schema_status = "success"
        schema_summary = "PanelRequest 强类型校验通过"
    elif llm_status == "error":
        schema_status = "skipped"
        schema_summary = "模型阶段失败，未进入参数校验"
    else:
        schema_status = "error"
        schema_summary = "参数未通过 PanelRequest 校验"

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

    if mode != "mcp":
        mcp_status = "skipped"
        mcp_summary = "当前使用 Direct Mock，未经过 MCP"
    elif mcp_request is None:
        mcp_status = "skipped"
        mcp_summary = "本地校验或配置检查已阻止 MCP 调用"
    elif cad_result is not None and cad_result.success:
        mcp_status = "success"
        mcp_summary = "tools/call 已通过 STDIO 完成"
    else:
        mcp_status = "error"
        mcp_summary = "MCP 已返回业务失败" if mcp_response else "已尝试 MCP 调用，未获得有效结果"

    if mode == "mcp":
        provider = "contract-mock"
        provider_label = "Contract Mock"
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

    graph_status = "error" if status == "error" and llm_status == "error" else (
        "attention" if status == "clarification" else "success"
    )
    graph_summary = {
        "success": "路由：parse -> validate -> cad",
        "clarification": "路由：parse -> validate -> END",
        "unsupported": "路由：parse -> validate -> END",
        "error": (
            "路由在模型阶段受控停止"
            if llm_status == "error"
            else "路由在执行阶段受控停止"
        ),
    }[status]

    nodes = [
        TraceNodeView(
            name="llm",
            label="Local Qwen",
            status=llm_status,
            duration_ms=_optional_duration(trace.get("llm_duration_ms")),
            summary="本地模型已生成结构化候选参数"
            if llm_status == "success"
            else "本地模型未返回可用参数",
            details={"model": "qwen2.5:7b", "data": "candidate parameters only"},
        ),
        TraceNodeView(
            name="graph",
            label="LangGraph",
            status=graph_status,
            summary=graph_summary,
            details={"policy": "validated requests only"},
        ),
        TraceNodeView(
            name="schema",
            label="Pydantic Schema",
            status=schema_status,
            summary=schema_summary,
            details={"schema": "PanelRequest", "extra": "forbid"},
        ),
        TraceNodeView(
            name="mcp",
            label="MCP STDIO",
            status=mcp_status,
            duration_ms=_optional_duration(trace.get("mcp_duration_ms")),
            summary=mcp_summary,
            details={"transport": "stdio", "tool": "create_panel"},
        ),
        TraceNodeView(
            name="provider",
            label=provider_label,
            status=provider_status,
            summary=provider_summary,
            details={"simulated": True},
        ),
    ]
    return ExecutionTraceView(
        nodes=nodes,
        mcp_request=mcp_request,
        mcp_response=mcp_response,
        provider=provider,
        total_ms=_optional_duration(trace.get("total_ms")),
    )


def _optional_duration(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, round(value))
