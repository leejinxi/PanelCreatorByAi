import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent.main import run_panel_agent
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


def create_app(
    *,
    agent_runner: AgentRunner = run_panel_agent,
    mode: ExecutionMode = "mock",
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
    def health() -> HealthResponse:
        return HealthResponse(
            mode=mode,
            cad_backend="mock" if mode == "mock" else "connector",
        )

    @application.post(
        "/api/agent/runs",
        response_model=AgentRunResponse,
    )
    def run_agent(request: AgentRunRequest) -> AgentRunResponse | JSONResponse:
        request_id = uuid4().hex

        try:
            state = agent_runner(request.message)
        except Exception:
            logger.exception(
                "Unexpected web agent failure for request %s",
                request_id,
            )
            response = map_agent_state(
                {
                    "error": "Agent 服务发生未预期异常。",
                    "error_code": "AGENT_INTERNAL_ERROR",
                },
                request_id=request_id,
                mode=mode,
            )
            return JSONResponse(
                status_code=500,
                content=response.model_dump(mode="json", by_alias=True),
            )

        return map_agent_state(
            state,
            request_id=request_id,
            mode=mode,
        )

    return application


app = create_app()
