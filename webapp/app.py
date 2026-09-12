import logging
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent.main import run_panel_agent
from tools.cad_tools import get_cad_backend_name
from agent.execution_trace import begin_trace, end_trace, snapshot_trace
from webapp.response_mapper import map_agent_state
from webapp.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ExecutionMode,
    HealthResponse,
)


logger = logging.getLogger(__name__)
AgentRunner = Callable[[str], dict[str, Any]]
STATIC_DIR = Path(__file__).resolve().parent / "static"


def execution_mode() -> ExecutionMode:
    """报告配置的执行模式，不探测 MCP 或 CAD 连通性。"""
    name = get_cad_backend_name()
    return name if name in {"mock", "mcp"} else "unconfigured"


def create_app(
    *,
    agent_runner: AgentRunner = run_panel_agent,
) -> FastAPI:
    """创建可注入 Agent Runner 的 Web 应用，便于测试和替换后端。"""

    application = FastAPI(
        title="AI Ship CAD Copilot API",
        version="0.1.0",
        description="本地板架创建 Agent 的浏览器接口。",
    )
    application.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static",
    )

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get(
        "/api/health",
        response_model=HealthResponse,
    )
    def health() -> HealthResponse | JSONResponse:
        mode = execution_mode()
        result = HealthResponse(
            status="error" if mode == "unconfigured" else "ok",
            mode=mode,
            cad_backend={"mock": "mock", "mcp": "mcp-contract-mock",
                         "unconfigured": "unconfigured"}[mode],
        )
        if mode == "unconfigured":
            return JSONResponse(status_code=503, content=result.model_dump())
        return result

    @application.post(
        "/api/agent/runs",
        response_model=AgentRunResponse,
    )
    def run_agent(request: AgentRunRequest) -> AgentRunResponse | JSONResponse:
        request_id = uuid4().hex
        mode = execution_mode()

        provider = {
            "mock": "direct-mock",
            "mcp": "contract-mock",
            "unconfigured": "unconfigured",
        }[mode]
        token = begin_trace(provider)
        started = perf_counter()
        try:
            state = agent_runner(request.message)
            trace = snapshot_trace()
            trace["total_ms"] = round((perf_counter() - started) * 1000)
            return map_agent_state(
                state,
                request_id=request_id,
                mode=mode,
                trace=trace,
            )
        except Exception:
            logger.exception(
                "Unexpected web agent failure for request %s",
                request_id,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "request_id": request_id,
                    "status": "error",
                    "mode": mode,
                    "message": "Agent 服务发生未预期异常。",
                    "steps": [
                        {"name": "parse", "status": "error"},
                        {"name": "decision", "status": "skipped"},
                        {"name": "inspect", "status": "skipped"},
                        {"name": "review", "status": "skipped"},
                        {"name": "evaluate", "status": "skipped"},
                        {"name": "validate", "status": "skipped"},
                        {"name": "cad", "status": "skipped"},
                    ],
                    "panel": None,
                    "cad_result": None,
                    "error_code": "AGENT_INTERNAL_ERROR",
                    "execution_trace": {
                        "nodes": [
                            {
                                "name": "qwen_parse",
                                "label": "Qwen 参数解析",
                                "status": "error",
                                "summary": "请求发生未预期异常",
                            },
                            {
                                "name": "policy_decision",
                                "label": "Agent 首次决策",
                                "status": "skipped",
                                "summary": "未形成首次决策",
                            },
                            {
                                "name": "project_context",
                                "label": "Mock 工程查询",
                                "status": "skipped",
                                "summary": "未执行工程查询",
                            },
                            {
                                "name": "design_review",
                                "label": "板架智能评审",
                                "status": "skipped",
                                "summary": "未执行创建前评审",
                            },
                            {
                                "name": "qwen_decision",
                                "label": "Qwen 结果评估",
                                "status": "skipped",
                                "summary": "未执行结果评估",
                            },
                            {
                                "name": "safety_gate",
                                "label": "Safety Gate",
                                "status": "skipped",
                                "summary": "未进入执行授权",
                            },
                            {
                                "name": "provider",
                                "label": "CAD Provider",
                                "status": "skipped",
                                "summary": "未执行 Provider",
                            },
                        ],
                        "provider": provider,
                        "simulated": True,
                        "total_ms": round((perf_counter() - started) * 1000),
                    },
                },
            )
        finally:
            end_trace(token)

    return application


app = create_app()
