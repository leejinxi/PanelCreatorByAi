"""请求级展示 Trace；只记录允许返回页面的白名单字段。"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from copy import deepcopy
from collections.abc import Iterator
from typing import Any, Literal


_TRACE: ContextVar[dict[str, Any] | None] = ContextVar("execution_trace", default=None)
_LLM_PHASE: ContextVar[str] = ContextVar("llm_trace_phase", default="unknown")


def begin_trace(provider: str) -> Token:
    return _TRACE.set({
        "provider": provider,
        "llm_duration_ms": None,
        "llm_call_count": 0,
        "llm_calls": [],
        "mcp_duration_ms": None,
        "mcp_request": None,
        "mcp_response": None,
    })


def end_trace(token: Token) -> None:
    _TRACE.reset(token)


@contextmanager
def llm_trace_phase(
    phase: Literal["parse", "decision"],
) -> Iterator[None]:
    """标记一次模型调用的展示阶段，不记录 Prompt 或模型原文。"""

    token = _LLM_PHASE.set(phase)
    try:
        yield
    finally:
        _LLM_PHASE.reset(token)


def record_llm(duration_ms: int) -> None:
    trace = _TRACE.get()
    if trace is not None:
        bounded_duration = max(0, duration_ms)
        previous = trace.get("llm_duration_ms")
        trace["llm_duration_ms"] = bounded_duration + (
            previous if isinstance(previous, int) else 0
        )
        trace["llm_call_count"] = int(trace.get("llm_call_count", 0)) + 1
        trace.setdefault("llm_calls", []).append({
            "phase": _LLM_PHASE.get(),
            "duration_ms": bounded_duration,
        })


def record_mcp_request(arguments: dict[str, Any], contract_version: str) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace["mcp_request"] = {
            "transport": "stdio",
            "method": "tools/call",
            "tool": "create_panel",
            "contract_version": contract_version,
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
