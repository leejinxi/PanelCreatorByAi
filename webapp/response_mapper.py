from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from schemas.panel_schema import CadExecutionResult, PanelRequest
from webapp.schemas import (
    AgentRunResponse,
    AgentRunStatus,
    AgentStepView,
    BoundaryView,
    CadResultView,
    ExecutionMode,
    PanelView,
)


def map_agent_state(
    state: Mapping[str, Any],
    *,
    request_id: str,
    mode: ExecutionMode = "mock",
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
    if not isinstance(boundaries, Mapping):
        boundaries = {}

    try:
        return PanelView(
            reference_name=_optional_text(data.get("reference_plane")),
            thickness_mm=data.get("thickness"),
            material=_optional_text(data.get("material")),
            boundaries=BoundaryView.model_validate(boundaries),
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
