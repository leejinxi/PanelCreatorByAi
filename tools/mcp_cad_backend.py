from pathlib import Path

from pydantic import ValidationError

from mcp_client.stdio_client import McpProtocolError, StdioMcpClient
from schemas.panel_schema import CadExecutionResult, PanelRequest
from tools.cad_tools import CadBackendError


class McpCadBackend:
    """CadBackend implementation backed by the local MCP contract server."""

    def __init__(self, contract_path: Path, timeout_seconds: float = 10.0) -> None:
        self.client = StdioMcpClient(contract_path, timeout_seconds)

    def create_panel(self, panel: PanelRequest) -> str:
        arguments = {
            "referenceName": panel.reference_plane,
            "thicknessMm": panel.thickness,
            "material": panel.material,
            "boundaries": panel.boundaries.model_dump(),
        }
        try:
            payload = self.client.call_tool("create_panel", arguments)
        except TimeoutError as exc:
            raise CadBackendError("MCP call timed out.", error_code="MCP_TIMEOUT") from exc
        except Exception as exc:
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
