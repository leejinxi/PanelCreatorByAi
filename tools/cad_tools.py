import logging
from typing import Protocol
from uuid import uuid4

from schemas.panel_schema import CadExecutionResult, PanelRequest


logger = logging.getLogger(__name__)


class CadBackendError(Exception):
    """CAD 后端可预期的业务或通信异常。"""

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class CadBackend(Protocol):
    """Mock、MCP 和真实 CAD 后端共同遵守的最小接口。"""

    def create_panel(self, panel: PanelRequest) -> str:
        """创建板架并返回 CAD 对象 ID。"""


class MockCadBackend:
    """不连接真实 CAD 的本地开发后端。"""

    def create_panel(self, panel: PanelRequest) -> str:
        object_id = f"mock-panel-{uuid4().hex}"
        logger.info(
            "Mock CAD created panel %s on reference plane %s",
            object_id,
            panel.reference_plane,
        )
        return object_id


class CreatePanelTool:
    """稳定工具契约与具体 CAD 后端之间的适配层。"""

    name = "create_panel"
    description = "使用已校验的板架参数和工程定位面名称创建板架。"
    args_schema = PanelRequest

    def __init__(self, backend: CadBackend) -> None:
        self._backend = backend

    def invoke(self, panel: PanelRequest) -> CadExecutionResult:
        try:
            object_id = self._backend.create_panel(panel)
            if not isinstance(object_id, str) or not object_id.strip():
                raise CadBackendError(
                    "CAD 后端没有返回有效的板架对象 ID。",
                    error_code="CAD_INVALID_RESPONSE",
                )
        except CadBackendError as exc:
            logger.warning("CAD panel creation failed: %s", exc)
            return CadExecutionResult(
                success=False,
                message=str(exc),
                error_code=exc.error_code,
            )
        except Exception:
            logger.exception("Unexpected CAD panel creation failure")
            return CadExecutionResult(
                success=False,
                message="CAD 后端发生未预期异常。",
                error_code="CAD_INTERNAL_ERROR",
            )

        return CadExecutionResult(
            success=True,
            message="Panel created successfully",
            object_id=object_id,
        )


_default_tool = CreatePanelTool(MockCadBackend())


def create_panel(panel: PanelRequest) -> CadExecutionResult:
    """执行板架创建；未来可在不改变调用方的情况下替换后端。"""

    return _default_tool.invoke(panel)
