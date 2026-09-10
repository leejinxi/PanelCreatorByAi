from pathlib import Path
from time import perf_counter

from pydantic import ValidationError
from mcp_mock.contract import load_contract

from mcp_client.stdio_client import McpProtocolError, StdioMcpClient
from schemas.panel_schema import CadExecutionResult, PanelRequest
from tools.cad_tools import CadBackendError
from agent.execution_trace import (
    record_mcp_duration,
    record_mcp_request,
    record_mcp_response,
)


class McpCadBackend:
    """CadBackend implementation backed by the local MCP contract server."""

    def __init__(self, contract_path: Path, timeout_seconds: float = 10.0) -> None:
        self.client = StdioMcpClient(contract_path, timeout_seconds)

    def create_panel(self, panel: PanelRequest) -> str:
        try:
            contract = load_contract(self.client.contract_path)
            definition = next(tool for tool in contract['tools'] if tool['name'] == 'create_panel')
        except (ValueError, KeyError, StopIteration, OSError) as exc:
            raise CadBackendError('MCP 契约未确认或无法加载。', error_code='CAD_BACKEND_CONFIG_ERROR') from exc
        if definition['inputSchema']['properties']['boundaries'].get('type') != 'array':
            raise CadBackendError(
                '当前 MCP 契约仍使用四向边界，不能接收边界列表。请先完成新版契约确认；可使用 Direct Mock 验证本地流程。',
                error_code='MCP_CONTRACT_INCOMPATIBLE',
            )
        arguments = {
            "referenceName": panel.reference_plane,
            "thicknessMm": panel.thickness,
            "material": panel.material,
            "boundaries": [item.model_dump() for item in panel.boundaries],
        }
        record_mcp_request(arguments, contract['contractVersion'])
        started = perf_counter()
        try:
            payload = self.client.call_tool("create_panel", arguments)
            record_mcp_response(
                payload,
                round((perf_counter() - started) * 1000),
            )
        except TimeoutError as exc:
            record_mcp_duration(round((perf_counter() - started) * 1000))
            raise CadBackendError("MCP call timed out.", error_code="MCP_TIMEOUT") from exc
        except McpProtocolError as exc:
            record_mcp_duration(round((perf_counter() - started) * 1000))
            raise CadBackendError('MCP 响应协议无效。', error_code='MCP_INVALID_RESPONSE') from exc
        except Exception as exc:
            record_mcp_duration(round((perf_counter() - started) * 1000))
            raise CadBackendError("MCP server is unavailable.", error_code="MCP_UNAVAILABLE") from exc

        try:
            result = CadExecutionResult.model_validate(
                {
                    "success": payload.get("success"),
                    "message": payload.get("message"),
                    "object_id": payload.get("objectId"),
                    "error_code": payload.get("errorCode"),
                }
            )
        except (AttributeError, ValidationError) as exc:
            raise CadBackendError(
                "MCP response does not match the CAD result contract.",
                error_code="MCP_INVALID_RESPONSE",
            ) from exc

        if not result.success:
            raise CadBackendError(result.message, error_code=result.error_code)
        if result.object_id is None:
            raise CadBackendError(
                "MCP response does not contain a panel object ID.",
                error_code="MCP_INVALID_RESPONSE",
            )
        return result.object_id
