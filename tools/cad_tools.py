import logging
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from schemas.panel_schema import CadExecutionResult, PanelRequest


logger = logging.getLogger(__name__)

DEFAULT_MCP_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "boundary_list_0.2.json"
)
DEFAULT_MCP_TIMEOUT_SECONDS = 10.0


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


def get_cad_backend_name(environ: Mapping[str, str] | None = None) -> str:
    """读取后端选择，供执行层和状态接口共用；不连接后端。"""
    settings = os.environ if environ is None else environ
    return settings.get("CAD_BACKEND", "mock").strip().lower()


def build_cad_backend(
    environ: Mapping[str, str] | None = None,
) -> CadBackend:
    """根据运行时配置构造 CAD 后端；默认使用直接 Mock。"""

    settings = os.environ if environ is None else environ
    backend_name = get_cad_backend_name(settings)

    if backend_name == "mock":
        return MockCadBackend()
    if backend_name != "mcp":
        raise CadBackendError(
            f"不支持的 CAD_BACKEND：{backend_name or '<empty>'}。",
            error_code="CAD_BACKEND_CONFIG_ERROR",
        )

    contract_value = settings.get("MCP_CONTRACT_PATH", "").strip()
    contract_path = (
        Path(contract_value).expanduser()
        if contract_value
        else DEFAULT_MCP_CONTRACT_PATH
    )
    if not contract_path.is_file():
        raise CadBackendError(
            "MCP 契约文件不存在或不是文件。",
            error_code="CAD_BACKEND_CONFIG_ERROR",
        )

    timeout_value = settings.get(
        "MCP_TIMEOUT_SECONDS",
        str(DEFAULT_MCP_TIMEOUT_SECONDS),
    ).strip()
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise CadBackendError(
            "MCP_TIMEOUT_SECONDS 必须是有限的正数。",
            error_code="CAD_BACKEND_CONFIG_ERROR",
        ) from exc
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise CadBackendError(
            "MCP_TIMEOUT_SECONDS 必须是有限的正数。",
            error_code="CAD_BACKEND_CONFIG_ERROR",
        )

    # 延迟导入，避免 MCP 适配器与本模块的 CadBackendError 循环导入。
    from tools.mcp_cad_backend import McpCadBackend

    return McpCadBackend(contract_path, timeout_seconds)


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


def create_panel(panel: PanelRequest) -> CadExecutionResult:
    """按运行时配置选择后端并执行板架创建。"""

    try:
        backend = build_cad_backend()
    except CadBackendError as exc:
        logger.warning("CAD backend configuration failed: %s", exc)
        return CadExecutionResult(
            success=False,
            message=str(exc),
            error_code=exc.error_code,
        )
    return CreatePanelTool(backend).invoke(panel)
