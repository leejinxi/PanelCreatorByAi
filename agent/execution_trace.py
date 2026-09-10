"""请求级展示 Trace；只记录允许返回页面的白名单字段。"""

from contextvars import ContextVar, Token
from copy import deepcopy
from typing import Any


_TRACE: ContextVar[dict[str, Any] | None] = ContextVar("execution_trace", default=None)


def begin_trace(provider: str) -> Token:
    return _TRACE.set({
        "provider": provider,
        "llm_duration_ms": None,
        "mcp_duration_ms": None,
        "mcp_request": None,
        "mcp_response": None,
    })


def end_trace(token: Token) -> None:
    _TRACE.reset(token)


def record_llm(duration_ms: int) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace["llm_duration_ms"] = max(0, duration_ms)


def record_mcp_request(arguments: dict[str, Any]) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace["mcp_request"] = {
            "transport": "stdio",
            "method": "tools/call",
            "tool": "create_panel",
            "contract_version": "0.1-poc",
            "arguments": deepcopy(arguments),
        }


def record_mcp_response(payload: dict[str, Any], duration_ms: int) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace["mcp_duration_ms"] = max(0, duration_ms)
        trace["mcp_response"] = {
            "success": payload.get("success"),
            "object_id": payload.get("objectId"),
            "error_code": payload.get("errorCode"),
        }


def record_mcp_duration(duration_ms: int) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace["mcp_duration_ms"] = max(0, duration_ms)


def snapshot_trace() -> dict[str, Any]:
    return deepcopy(_TRACE.get() or {})
